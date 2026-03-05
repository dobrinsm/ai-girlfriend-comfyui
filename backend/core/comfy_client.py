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

# Maximum reconnect attempts with exponential backoff
MAX_RECONNECT_ATTEMPTS = 10
RECONNECT_BASE_DELAY = 1.0  # seconds


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
        # BUG FIX #3: Generate a stable client_id for this session so ComfyUI
        # routes WebSocket execution events back to this specific connection.
        self.client_id: str = str(uuid.uuid4())
        # Event map: prompt_id -> asyncio.Event, set when execution completes
        self._completion_events: Dict[str, asyncio.Event] = {}
        # Output map: prompt_id -> output data, populated on "executed" message
        self._outputs: Dict[str, Dict[str, Any]] = {}

    async def connect(self):
        """Establish WebSocket connection with retry logic"""
        attempt = 0
        while attempt < MAX_RECONNECT_ATTEMPTS:
            try:
                # BUG FIX #3: Include client_id as query param so ComfyUI routes
                # execution events to this WebSocket connection.
                ws_url = f"{self.websocket_url}?clientId={self.client_id}"
                self.ws = await websockets.connect(ws_url)
                self.is_connected = True
                self._listen_task = asyncio.create_task(self._listen())
                logger.info(
                    f"Connected to ComfyUI WebSocket (client_id={self.client_id})"
                )
                return
            except Exception as e:
                attempt += 1
                delay = RECONNECT_BASE_DELAY * (2 ** (attempt - 1))
                logger.error(
                    f"Failed to connect to ComfyUI (attempt {attempt}/{MAX_RECONNECT_ATTEMPTS}): {e}"
                )
                if attempt < MAX_RECONNECT_ATTEMPTS:
                    logger.info(f"Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                else:
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
        """Listen for WebSocket messages with auto-reconnect"""
        while self.is_connected:
            try:
                if self.ws:
                    message = await self.ws.recv()
                    # ComfyUI sends binary preview frames; skip non-JSON
                    if isinstance(message, bytes):
                        continue
                    data = json.loads(message)
                    await self._handle_message(data)
            except ConnectionClosed:
                logger.warning("WebSocket connection closed, attempting reconnect...")
                self.is_connected = False
                # Attempt reconnect in background
                asyncio.create_task(self._reconnect())
                break
            except Exception as e:
                logger.error(f"Error handling message: {e}")

    async def _reconnect(self):
        """Attempt to reconnect to ComfyUI WebSocket"""
        try:
            await self.connect()
        except Exception as e:
            logger.error(f"Reconnect failed: {e}")

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
            # Store output and signal waiting coroutines
            if prompt_id:
                self._outputs[prompt_id] = output
                event = self._completion_events.get(prompt_id)
                if event:
                    event.set()

        elif msg_type == "execution_error":
            prompt_id = data.get("data", {}).get("prompt_id")
            error = data.get("data", {}).get("error", "Unknown error")
            logger.error(f"Execution error ({prompt_id}): {error}")
            # Signal waiting coroutines even on error so they don't hang
            if prompt_id:
                event = self._completion_events.get(prompt_id)
                if event:
                    event.set()

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

        # Determine MIME type from extension
        suffix = path.suffix.lstrip(".").lower()
        mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}
        mime_type = f"image/{mime_map.get(suffix, suffix)}"

        files = {"image": (name, content, mime_type)}
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

        # BUG FIX #12: Use self.client_id (the WebSocket session ID) so ComfyUI
        # routes execution events to our connected WebSocket. The prompt_id is
        # returned by the API and used to poll history / match WS events.
        data = {
            "prompt": workflow,
            "client_id": self.client_id
        }

        response = await self.client.post(
            f"{self.base_url}/prompt",
            json=data
        )
        response.raise_for_status()

        result = response.json()
        returned_prompt_id = result.get("prompt_id")
        logger.info(f"Workflow queued: {returned_prompt_id}")
        return returned_prompt_id

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
        """
        Wait for and retrieve output file path.

        BUG FIX #4: Now handles images, gifs/videos, and audio outputs.
        Uses event-driven approach via WebSocket 'executed' message when
        connected, falling back to polling if not.
        """
        # Register a completion event for this prompt
        event = asyncio.Event()
        self._completion_events[prompt_id] = event

        try:
            # Wait for the WebSocket 'executed' event or timeout
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    f"WebSocket event timed out for {prompt_id}, falling back to polling"
                )

            # Check in-memory output first (populated by WS handler)
            if prompt_id in self._outputs:
                return self._extract_filename(self._outputs[prompt_id], node_id)

            # Fallback: poll history API
            deadline = asyncio.get_event_loop().time() + 30.0
            while asyncio.get_event_loop().time() < deadline:
                history = await self.get_history(prompt_id)
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    if node_id and node_id in outputs:
                        return self._extract_filename(outputs[node_id], None)
                    if outputs:
                        first_output = list(outputs.values())[0]
                        return self._extract_filename(first_output, None)
                await asyncio.sleep(0.5)

        finally:
            # Clean up event and output cache
            self._completion_events.pop(prompt_id, None)
            self._outputs.pop(prompt_id, None)

        raise TimeoutError(f"Output not received within {timeout}s for prompt {prompt_id}")

    def _extract_filename(
        self,
        output: Dict[str, Any],
        node_id: Optional[str]
    ) -> Optional[str]:
        """
        BUG FIX #4: Extract filename from any output type.
        ComfyUI outputs can contain 'images', 'gifs', 'videos', or 'audio'.
        """
        if not output:
            return None

        # If a specific node was requested, look it up
        if node_id and node_id in output:
            return self._extract_filename(output[node_id], None)

        # Handle images (Flux, SadTalker frames)
        if "images" in output:
            images = output["images"]
            if images:
                return images[0].get("filename")

        # Handle video/gif outputs (VHS_VideoCombine, Wan 2.2)
        if "gifs" in output:
            gifs = output["gifs"]
            if gifs:
                return gifs[0].get("filename")

        if "videos" in output:
            videos = output["videos"]
            if videos:
                return videos[0].get("filename")

        # Handle audio outputs (CosyVoice, SaveAudio)
        if "audio" in output:
            audio = output["audio"]
            if audio:
                return audio[0].get("filename") if isinstance(audio, list) else audio.get("filename")

        # Generic fallback: return first filename found in any list value
        for key, value in output.items():
            if isinstance(value, list) and value:
                item = value[0]
                if isinstance(item, dict) and "filename" in item:
                    return item["filename"]

        return None

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
