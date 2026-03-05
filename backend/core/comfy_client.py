"""
ComfyUI WebSocket client for workflow execution
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import aiofiles
import httpx
import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


class ComfyUIClient:
    """Async ComfyUI client with WebSocket support"""

    def __init__(self, base_url: str, websocket_url: str):
        self.base_url = base_url.rstrip("/")
        self.websocket_url = websocket_url
        self.client = httpx.AsyncClient(timeout=300.0)
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.message_handlers: List[Callable] = []
        self._listen_task: Optional[asyncio.Task] = None

    async def connect(self):
        """Establish WebSocket connection"""
        try:
            self.ws = await websockets.connect(self.websocket_url)
            self.is_connected = True
            self._listen_task = asyncio.create_task(self._listen())
            logger.info("Connected to ComfyUI WebSocket")
        except Exception as e:
            logger.error(f"Failed to connect to ComfyUI: {e}")
            raise

    async def disconnect(self):
        """Close WebSocket connection"""
        self.is_connected = False
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            await self.ws.close()
        await self.client.aclose()
        logger.info("Disconnected from ComfyUI")

    async def _listen(self):
        """Listen for WebSocket messages"""
        while self.is_connected:
            try:
                if self.ws:
                    message = await self.ws.recv()
                    data = json.loads(message)
                    await self._handle_message(data)
            except ConnectionClosed:
                logger.warning("WebSocket connection closed")
                self.is_connected = False
                break
            except Exception as e:
                logger.error(f"Error handling message: {e}")

    async def _handle_message(self, data: Dict[str, Any]):
        """Handle incoming WebSocket message"""
        msg_type = data.get("type")

        if msg_type == "status":
            status = data.get("data", {}).get("status", {})
            logger.debug(f"ComfyUI status: {status}")

        elif msg_type == "execution_start":
            prompt_id = data.get("data", {}).get("prompt_id")
            logger.info(f"Execution started: {prompt_id}")

        elif msg_type == "executing":
            node = data.get("data", {}).get("node")
            logger.debug(f"Executing node: {node}")

        elif msg_type == "progress":
            value = data.get("data", {}).get("value", 0)
            max_value = data.get("data", {}).get("max", 100)
            logger.debug(f"Progress: {value}/{max_value}")

        elif msg_type == "executed":
            prompt_id = data.get("data", {}).get("prompt_id")
            output = data.get("data", {}).get("output", {})
            logger.info(f"Execution completed: {prompt_id}")

        elif msg_type == "execution_error":
            prompt_id = data.get("data", {}).get("prompt_id")
            error = data.get("data", {}).get("error", "Unknown error")
            logger.error(f"Execution error ({prompt_id}): {error}")

        # Notify handlers
        for handler in self.message_handlers:
            try:
                await handler(data)
            except Exception as e:
                logger.error(f"Handler error: {e}")

    def add_message_handler(self, handler: Callable):
        """Add a message handler"""
        self.message_handlers.append(handler)

    def remove_message_handler(self, handler: Callable):
        """Remove a message handler"""
        if handler in self.message_handlers:
            self.message_handlers.remove(handler)

    async def get_available_models(self) -> List[str]:
        """Get list of available models"""
        response = await self.client.get(f"{self.base_url}/object_info/CheckpointLoaderSimple")
        data = response.json()

        models = []
        if "CheckpointLoaderSimple" in data:
            inputs = data["CheckpointLoaderSimple"].get("input", {})
            required = inputs.get("required", {})
            ckpt_name = required.get("ckpt_name", [[]])
            if ckpt_name:
                models = ckpt_name[0]

        return models

    async def upload_image(self, image_path: str, name: Optional[str] = None) -> str:
        """Upload an image to ComfyUI"""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        if name is None:
            name = path.name

        async with aiofiles.open(path, "rb") as f:
            content = await f.read()

        files = {"image": (name, content, f"image/{path.suffix[1:]}")}
        data = {"type": "input", "overwrite": "true"}

        response = await self.client.post(
            f"{self.base_url}/upload/image",
            files=files,
            data=data
        )
        response.raise_for_status()

        result = response.json()
        return result.get("name", name)

    async def queue_workflow(
        self,
        workflow: Dict[str, Any],
        prompt_id: Optional[str] = None
    ) -> str:
        """Queue a workflow for execution"""
        if prompt_id is None:
            prompt_id = str(uuid.uuid4())

        data = {
            "prompt": workflow,
            "client_id": prompt_id
        }

        response = await self.client.post(
            f"{self.base_url}/prompt",
            json=data
        )
        response.raise_for_status()

        result = response.json()
        logger.info(f"Workflow queued: {result.get('prompt_id')}")
        return result.get("prompt_id")

    async def get_history(self, prompt_id: str) -> Dict[str, Any]:
        """Get execution history for a prompt"""
        response = await self.client.get(f"{self.base_url}/history/{prompt_id}")
        response.raise_for_status()
        return response.json()

    async def get_output(
        self,
        prompt_id: str,
        node_id: Optional[str] = None,
        timeout: float = 300.0
    ) -> Optional[str]:
        """Wait for and retrieve output file path"""
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            history = await self.get_history(prompt_id)

            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})

                if node_id and node_id in outputs:
                    return outputs[node_id]

                # Return first output if no specific node requested
                if outputs:
                    first_output = list(outputs.values())[0]
                    if "images" in first_output:
                        return first_output["images"][0].get("filename")

            await asyncio.sleep(0.5)

        raise TimeoutError(f"Output not received within {timeout}s")

    async def interrupt(self):
        """Interrupt current execution"""
        response = await self.client.post(f"{self.base_url}/interrupt")
        return response.status_code == 200

    async def free_memory(self, unload_models: bool = True, free_memory: bool = True):
        """Free ComfyUI memory"""
        data = {
            "unload_models": unload_models,
            "free_memory": free_memory
        }
        response = await self.client.post(f"{self.base_url}/free", json=data)
        return response.status_code == 200
