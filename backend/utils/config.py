"""
Configuration management for AI Girlfriend backend
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # App
    app_version: str = "1.0.0"
    app_name: str = "AI Girlfriend API"
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # ComfyUI
    comfyui_url: str = Field(default="http://localhost:8188", alias="COMFYUI_URL")
    comfyui_ws_url: str = Field(default="ws://localhost:8188/ws", alias="COMFYUI_WS_URL")
    workflow_dir: str = Field(default="../workflows", alias="WORKFLOW_DIR")
    output_dir: str = Field(default="./outputs", alias="OUTPUT_DIR")

    # Models
    vlm_model: str = Field(default="qwen2-vl-7b", alias="VLM_MODEL")
    llm_model: str = Field(default="mistral", alias="LLM_MODEL")
    tts_model: str = Field(default="cosyvoice3", alias="TTS_MODEL")
    tts_voice_id: str = Field(default="friendly_female", alias="TTS_VOICE_ID")

    # Memory
    memory_db_path: str = Field(default="./data/memory.db", alias="MEMORY_DB_PATH")
    max_memory_items: int = Field(default=50, alias="MAX_MEMORY_ITEMS")

    # Generation settings
    default_cfg: float = Field(default=3.5, alias="DEFAULT_CFG")
    default_steps: int = Field(default=6, alias="DEFAULT_STEPS")
    wavespeed_cache: bool = Field(default=True, alias="WAVESPEED_CACHE")
    cache_strength: float = Field(default=0.15, alias="CACHE_STRENGTH")

    # Performance
    max_concurrent_generations: int = Field(default=2, alias="MAX_CONCURRENT_GENERATIONS")
    request_timeout: int = Field(default=300, alias="REQUEST_TIMEOUT")

    # Redis (optional, for scaling)
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")

    # Security
    api_key: Optional[str] = Field(default=None, alias="API_KEY")
    allowed_origins: List[str] = Field(default=["*"], alias="ALLOWED_ORIGINS")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
