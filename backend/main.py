#!/usr/bin/env python3
"""
AI Girlfriend - FastAPI Backend
Real-time avatar generation pipeline orchestration
"""

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from core.comfy_client import ComfyUIClient
from core.pipeline import PipelineManager
from core.memory import MemoryManager
from core.vlm import VLMProcessor
from core.tts import TTSProcessor
from utils.config import Settings, get_settings
from utils.logger import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Global state
comfy_client: Optional[ComfyUIClient] = None
pipeline_manager: Optional[PipelineManager] = None
memory_manager: Optional[MemoryManager] = None
vlm_processor: Optional[VLMProcessor] = None
tts_processor: Optional[TTSProcessor] = None


async def _connect_comfyui_with_retry(
    comfy_client: ComfyUIClient,
    max_attempts: int = 10,
    base_delay: float = 3.0
):
    """
    Enhancement: Retry ComfyUI connection on startup so the backend doesn't
    crash if ComfyUI takes a moment to become ready (common in Docker Compose).
    """
    for attempt in range(1, max_attempts + 1):
        try:
            await comfy_client.connect()
            return
        except Exception as e:
            delay = base_delay * attempt
            logger.warning(
                f"ComfyUI not ready (attempt {attempt}/{max_attempts}): {e}. "
                f"Retrying in {delay:.0f}s..."
            )
            if attempt == max_attempts:
                raise
            await asyncio.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager"""
    global comfy_client, pipeline_manager, memory_manager, vlm_processor, tts_processor

    settings = get_settings()
    logger.info(f"Starting AI Girlfriend Backend v{settings.app_version}")

    # Initialize components
    try:
        memory_manager = MemoryManager(db_path=settings.memory_db_path)
        await memory_manager.initialize()
        logger.info("Memory manager initialized")

        comfy_client = ComfyUIClient(
            base_url=settings.comfyui_url,
            websocket_url=settings.comfyui_ws_url
        )
        # Enhancement: graceful retry instead of hard crash on startup
        await _connect_comfyui_with_retry(comfy_client)
        logger.info(f"Connected to ComfyUI at {settings.comfyui_url}")

        vlm_processor = VLMProcessor(model_name=settings.vlm_model)
        logger.info(f"VLM processor initialized with {settings.vlm_model}")

        tts_processor = TTSProcessor(
            model_name=settings.tts_model,
            voice_id=settings.tts_voice_id
        )
        logger.info(f"TTS processor initialized with {settings.tts_model}")

        pipeline_manager = PipelineManager(
            comfy_client=comfy_client,
            memory_manager=memory_manager,
            vlm_processor=vlm_processor,
            tts_processor=tts_processor,
            workflow_dir=settings.workflow_dir,
            # BUG FIX #8: Pass llm_model from settings
            llm_model=settings.llm_model
        )
        logger.info("Pipeline manager initialized")

    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        raise

    yield

    # Cleanup
    logger.info("Shutting down...")
    if comfy_client:
        await comfy_client.disconnect()
    if memory_manager:
        await memory_manager.close()


app = FastAPI(
    title="AI Girlfriend API",
    description="Real-time avatar generation with ComfyUI + WaveSpeed",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "comfyui_connected": comfy_client.is_connected if comfy_client else False
    }


@app.get("/api/v1/models")
async def list_models():
    """List available models in ComfyUI"""
    if not comfy_client:
        raise HTTPException(status_code=503, detail="ComfyUI not connected")

    try:
        models = await comfy_client.get_available_models()
        return {"models": models}
    except Exception as e:
        logger.error(f"Failed to get models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/generate/avatar")
async def generate_avatar(
    prompt: str = Form(...),
    webcam_image: Optional[UploadFile] = File(None),
    user_id: str = Form("default_user"),
    use_ip_adapter: bool = Form(True)
):
    """
    Generate avatar image from prompt with optional webcam input for IP-Adapter
    """
    if not pipeline_manager:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    try:
        request_id = str(uuid.uuid4())

        # Save webcam image if provided
        webcam_path = None
        if webcam_image:
            upload_dir = Path("uploads") / user_id
            upload_dir.mkdir(parents=True, exist_ok=True)
            webcam_path = upload_dir / f"{request_id}_webcam.png"
            content = await webcam_image.read()
            webcam_path.write_bytes(content)

        # Queue generation
        result = await pipeline_manager.generate_avatar(
            request_id=request_id,
            prompt=prompt,
            user_id=user_id,
            webcam_path=str(webcam_path) if webcam_path else None,
            use_ip_adapter=use_ip_adapter
        )

        return {
            "request_id": request_id,
            "status": "completed",
            "output_path": result.get("output_path"),
            "generation_time": result.get("generation_time"),
            "prompt_used": result.get("prompt")
        }

    except Exception as e:
        logger.error(f"Avatar generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/generate/video")
async def generate_video(
    image_path: str,
    prompt: str = "",
    duration: int = 2,
    user_id: str = "default_user"
):
    """
    Generate video from image using Wan 2.2 I2V
    """
    if not pipeline_manager:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    try:
        request_id = str(uuid.uuid4())

        result = await pipeline_manager.generate_video(
            request_id=request_id,
            image_path=image_path,
            prompt=prompt,
            duration=duration,
            user_id=user_id
        )

        return {
            "request_id": request_id,
            "status": "completed",
            "video_path": result.get("video_path"),
            "generation_time": result.get("generation_time")
        }

    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/generate/voice")
async def generate_voice(
    text: str,
    user_id: str = "default_user",
    emotion: str = "neutral"
):
    """
    Generate voice using CosyVoice3/Dia TTS
    """
    if not tts_processor:
        raise HTTPException(status_code=503, detail="TTS not initialized")

    try:
        request_id = str(uuid.uuid4())

        audio_path = await tts_processor.generate(
            text=text,
            request_id=request_id,
            user_id=user_id,
            emotion=emotion
        )

        return {
            "request_id": request_id,
            "audio_path": audio_path,
            "status": "completed"
        }

    except Exception as e:
        logger.error(f"Voice generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/generate/lipsync")
async def generate_lipsync(
    image_path: str,
    audio_path: str,
    user_id: str = "default_user"
):
    """
    Generate lip-synced video using SadTalker
    """
    if not pipeline_manager:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    try:
        request_id = str(uuid.uuid4())

        result = await pipeline_manager.generate_lipsync(
            request_id=request_id,
            image_path=image_path,
            audio_path=audio_path,
            user_id=user_id
        )

        return {
            "request_id": request_id,
            "status": "completed",
            "video_path": result.get("video_path"),
            "generation_time": result.get("generation_time")
        }

    except Exception as e:
        logger.error(f"Lip-sync generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for real-time chat with avatar generation
    """
    await websocket.accept()
    user_id = None
    logger.info("[WS] Client connected to WebSocket")

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            logger.info(f"[WS] Received data: {data}")
            message_type = data.get("type", "message")
            user_id = data.get("user_id", "anonymous")
            logger.info(f"[WS] message_type={message_type}, user_id={user_id}")

            if message_type == "chat":
                user_message = data.get("message", "")
                webcam_frame = data.get("webcam_frame")  # base64 encoded
                logger.info(f"[WS] Processing chat message: {user_message[:50]}...")

                # Process through pipeline
                async for update in pipeline_manager.process_chat_message(
                    user_id=user_id,
                    message=user_message,
                    webcam_frame=webcam_frame
                ):
                    logger.info(f"[WS] Yielding update: {update}")
                    await websocket.send_json(update)

            elif message_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"[WS] Client disconnected: {user_id}")
    except Exception as e:
        logger.error(f"[WS] WebSocket error: {e}", exc_info=True)
        await websocket.close(code=1011)


@app.get("/api/v1/memory/{user_id}")
async def get_user_memory(user_id: str, limit: int = 10):
    """Get conversation memory for user"""
    if not memory_manager:
        raise HTTPException(status_code=503, detail="Memory not initialized")

    try:
        memories = await memory_manager.get_memories(user_id, limit=limit)
        return {"user_id": user_id, "memories": memories}
    except Exception as e:
        logger.error(f"Failed to get memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/memory/{user_id}")
async def clear_user_memory(user_id: str):
    """Clear conversation memory for user"""
    if not memory_manager:
        raise HTTPException(status_code=503, detail="Memory not initialized")

    try:
        await memory_manager.clear_memories(user_id)
        return {"status": "cleared", "user_id": user_id}
    except Exception as e:
        logger.error(f"Failed to clear memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/workflows")
async def list_workflows():
    """List available ComfyUI workflows"""
    settings = get_settings()
    workflow_dir = Path(settings.workflow_dir)

    workflows = []
    for category_dir in workflow_dir.iterdir():
        if category_dir.is_dir():
            category_workflows = []
            for wf_file in category_dir.glob("*.json"):
                category_workflows.append({
                    "name": wf_file.stem,
                    "path": str(wf_file.relative_to(workflow_dir))
                })
            workflows.append({
                "category": category_dir.name,
                "workflows": category_workflows
            })

    return {"workflows": workflows}


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
