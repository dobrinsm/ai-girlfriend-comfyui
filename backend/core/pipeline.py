"""
Pipeline manager for orchestrating the AI girlfriend workflow
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Optional

from core.comfy_client import ComfyUIClient
from core.memory import MemoryManager
from core.vlm import VLMProcessor
from core.tts import TTSProcessor

logger = logging.getLogger(__name__)


class PipelineManager:
    """Manages the complete generation pipeline"""

    def __init__(
        self,
        comfy_client: ComfyUIClient,
        memory_manager: MemoryManager,
        vlm_processor: VLMProcessor,
        tts_processor: TTSProcessor,
        workflow_dir: str,
        llm_model: str = "llama3.2:7b"
    ):
        self.comfy = comfy_client
        self.memory = memory_manager
        self.vlm = vlm_processor
        self.tts = tts_processor
        self.workflow_dir = Path(workflow_dir)
        # BUG FIX #8: Store llm_model from settings instead of hardcoding
        self.llm_model = llm_model
        self.semaphore = asyncio.Semaphore(2)  # Limit concurrent generations

    async def process_chat_message(
        self,
        user_id: str,
        message: str,
        webcam_frame: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a chat message through the complete pipeline
        Yields progress updates
        """
        logger.info(f"[PIPELINE] Starting process_chat_message for user_id={user_id}, message={message[:50]}...")
        start_time = time.time()

        # Step 1: Analyze webcam frame with VLM (if provided)
        visual_context = ""
        if webcam_frame:
            logger.info("[PIPELINE] Step 1: Analyzing webcam frame...")
            yield {"type": "status", "message": "Analyzing webcam..."}
            try:
                visual_context = await self.vlm.analyze_frame(webcam_frame)
                logger.info(f"[PIPELINE] VLM result: {visual_context}")
                yield {"type": "vlm_result", "context": visual_context}
            except Exception as e:
                logger.error(f"[PIPELINE] VLM analysis failed: {e}")

        # Step 2: Generate LLM response with memory
        logger.info("[PIPELINE] Step 2: Generating LLM response...")
        yield {"type": "status", "message": "Thinking..."}

        conversation_history = await self.memory.get_memories(user_id)

        # Build prompt with context
        system_prompt = """You are a friendly AI girlfriend having a natural conversation.
Be warm, empathetic, and engaging. Keep responses concise (1-2 sentences) for real-time interaction."""

        if visual_context:
            system_prompt += f"\n\nVisual context from webcam: {visual_context}"

        llm_response = await self._generate_llm_response(
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            user_message=message
        )

        yield {"type": "chat_response", "text": llm_response}

        # Step 3: Generate voice
        yield {"type": "status", "message": "Generating voice..."}
        try:
            audio_path = await self.tts.generate(
                text=llm_response,
                request_id=f"{user_id}_{int(time.time())}",
                user_id=user_id
            )
            yield {"type": "voice_ready", "audio_path": audio_path}
        except Exception as e:
            logger.error(f"Voice generation failed: {e}")
            audio_path = None

        # Step 4: Generate avatar (if webcam provided)
        avatar_path = None
        if webcam_frame:
            yield {"type": "status", "message": "Generating avatar..."}
            try:
                result = await self.generate_avatar(
                    request_id=f"{user_id}_{int(time.time())}",
                    prompt=f"friendly expression, {llm_response[:50]}",
                    user_id=user_id,
                    webcam_frame=webcam_frame
                )
                avatar_path = result.get("output_path")
                yield {"type": "avatar_ready", "image_path": avatar_path}
            except Exception as e:
                logger.error(f"Avatar generation failed: {e}")

        # Step 5: Generate video from avatar
        if avatar_path:
            yield {"type": "status", "message": "Animating..."}
            try:
                result = await self.generate_video(
                    request_id=f"{user_id}_{int(time.time())}",
                    image_path=avatar_path,
                    prompt=f"speaking naturally: {llm_response[:30]}",
                    user_id=user_id
                )
                yield {"type": "video_ready", "video_path": result.get("video_path")}

                # Step 6: Lip sync if we have audio
                if audio_path:
                    yield {"type": "status", "message": "Syncing lips..."}
                    lip_result = await self.generate_lipsync(
                        request_id=f"{user_id}_{int(time.time())}",
                        image_path=avatar_path,
                        audio_path=audio_path,
                        user_id=user_id
                    )
                    yield {"type": "lipsync_ready", "video_path": lip_result.get("video_path")}

            except Exception as e:
                logger.error(f"Video generation failed: {e}")

        # Save to memory
        await self.memory.add_memory(
            user_id=user_id,
            user_message=message,
            ai_response=llm_response,
            metadata={
                "visual_context": visual_context,
                "generation_time": time.time() - start_time
            }
        )

        yield {
            "type": "complete",
            "total_time": time.time() - start_time,
            "avatar_path": avatar_path,
            "audio_path": audio_path
        }

    async def _generate_llm_response(
        self,
        system_prompt: str,
        conversation_history: list,
        user_message: str
    ) -> str:
        """Generate LLM response using Ollama"""
        import ollama

        # BUG FIX #11: Memories are returned DESC (newest first) from DB.
        # Reverse them so the LLM sees conversation in chronological order.
        chronological_history = list(reversed(conversation_history[-5:]))

        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history in chronological order
        for mem in chronological_history:
            messages.append({"role": "user", "content": mem["user_message"]})
            messages.append({"role": "assistant", "content": mem["ai_response"]})

        messages.append({"role": "user", "content": user_message})

        # BUG FIX #8: Use self.llm_model from settings instead of hardcoded value.
        # Also respect OLLAMA_HOST env var for Docker deployments.
        ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        client = ollama.Client(host=ollama_host)

        response = await asyncio.to_thread(
            client.chat,
            model=self.llm_model,
            messages=messages,
            options={"temperature": 0.8, "num_predict": 150}
        )

        return response["message"]["content"]

    async def generate_avatar(
        self,
        request_id: str,
        prompt: str,
        user_id: str,
        webcam_path: Optional[str] = None,
        webcam_frame: Optional[str] = None,
        use_ip_adapter: bool = True
    ) -> Dict[str, Any]:
        """Generate avatar image using Flux + WaveSpeed"""
        async with self.semaphore:
            start_time = time.time()

            # Load workflow
            workflow_path = self.workflow_dir / "image-gen" / "flux_wavespeed_avatar.json"
            with open(workflow_path) as f:
                workflow = json.load(f)

            # BUG FIX #2: The workflow JSON uses a list of nodes (not a dict).
            # The previous code used .items() on a list which always fell through
            # to the empty else branch, meaning the prompt was never injected.
            # Now we iterate the list correctly and match by node type + position.
            nodes = workflow.get("nodes", [])
            for node in nodes:
                if node.get("type") == "CLIPTextEncode":
                    widgets = node.get("widgets_values", [])
                    # Node 2 (id=2) is the positive prompt; node 3 (id=3) is negative.
                    # Identify positive prompt node by absence of negative keywords.
                    if widgets and not any(
                        kw in str(widgets[0]).lower()
                        for kw in ["watermark", "blurry", "low quality", "ugly", "deformed"]
                    ):
                        node["widgets_values"] = [prompt]
                        break

            # Handle webcam input for IP-Adapter
            if use_ip_adapter and (webcam_path or webcam_frame):
                if webcam_frame:
                    # Save base64 frame to temp file
                    import base64
                    webcam_path = f"/tmp/{request_id}_webcam.png"
                    with open(webcam_path, "wb") as f:
                        f.write(base64.b64decode(webcam_frame.split(",")[-1]))

                # Upload to ComfyUI
                uploaded_name = await self.comfy.upload_image(
                    webcam_path, f"{request_id}_webcam.png"
                )

                # Update LoadImage node with uploaded filename
                for node in nodes:
                    if node.get("type") == "LoadImage":
                        node["widgets_values"] = [uploaded_name, "image"]

            # Queue workflow
            prompt_id = await self.comfy.queue_workflow(workflow, request_id)

            # Wait for output
            output_filename = await self.comfy.get_output(prompt_id)

            generation_time = time.time() - start_time
            logger.info(f"Avatar generated in {generation_time:.2f}s")

            return {
                "output_path": f"output/{output_filename}",
                "generation_time": generation_time,
                "prompt": prompt,
                "prompt_id": prompt_id
            }

    async def generate_video(
        self,
        request_id: str,
        image_path: str,
        prompt: str = "",
        duration: int = 2,
        user_id: str = "default_user"
    ) -> Dict[str, Any]:
        """Generate video using Wan 2.2 I2V + WaveSpeed"""
        async with self.semaphore:
            start_time = time.time()

            # Load workflow
            workflow_path = self.workflow_dir / "video-gen" / "wan22_i2v_wavespeed.json"
            with open(workflow_path) as f:
                workflow = json.load(f)

            # Upload input image
            uploaded_name = await self.comfy.upload_image(
                image_path, f"{request_id}_input.png"
            )

            # Update workflow nodes
            for node in workflow.get("nodes", []):
                if node.get("type") == "LoadImage":
                    node["widgets_values"] = [uploaded_name, "image"]
                elif node.get("type") == "CLIPTextEncode" and prompt:
                    widgets = node.get("widgets_values", [])
                    if widgets and not any(
                        kw in str(widgets[0]).lower()
                        for kw in ["blurry", "distorted", "unnatural", "robotic", "glitch"]
                    ):
                        node["widgets_values"] = [prompt]

            # Queue workflow
            prompt_id = await self.comfy.queue_workflow(workflow, request_id)

            # Wait for output
            output_filename = await self.comfy.get_output(prompt_id)

            generation_time = time.time() - start_time
            logger.info(f"Video generated in {generation_time:.2f}s")

            return {
                "video_path": f"output/{output_filename}",
                "generation_time": generation_time,
                "prompt": prompt
            }

    async def generate_lipsync(
        self,
        request_id: str,
        image_path: str,
        audio_path: str,
        user_id: str = "default_user"
    ) -> Dict[str, Any]:
        """Generate lip-synced video using SadTalker"""
        async with self.semaphore:
            start_time = time.time()

            # Load workflow
            workflow_path = self.workflow_dir / "voice-lipsync" / "cosyvoice_sadtalker_lipsync.json"
            with open(workflow_path) as f:
                workflow = json.load(f)

            # Upload files
            uploaded_image = await self.comfy.upload_image(
                image_path, f"{request_id}_avatar.png"
            )

            # Update workflow nodes
            for node in workflow.get("nodes", []):
                if node.get("type") == "LoadImage":
                    node["widgets_values"] = [uploaded_image, "image"]

            # Queue workflow
            prompt_id = await self.comfy.queue_workflow(workflow, request_id)

            # Wait for output
            output_filename = await self.comfy.get_output(prompt_id)

            generation_time = time.time() - start_time
            logger.info(f"Lip-sync generated in {generation_time:.2f}s")

            return {
                "video_path": f"output/{output_filename}",
                "generation_time": generation_time
            }
