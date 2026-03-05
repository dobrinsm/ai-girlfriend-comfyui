"""
Text-to-Speech processor using CosyVoice3 or Dia
"""

import base64
import io
import logging
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class TTSProcessor:
    """TTS processor supporting CosyVoice3 and Dia"""

    def __init__(
        self,
        model_name: str = "cosyvoice3",
        voice_id: str = "friendly_female",
        cosyvoice_server: Optional[str] = None
    ):
        self.model_name = model_name
        self.voice_id = voice_id
        self.cosyvoice_server = cosyvoice_server or "http://localhost:50000"
        self._client = httpx.AsyncClient(timeout=60.0)

    async def generate(
        self,
        text: str,
        request_id: str,
        user_id: str = "default_user",
        emotion: str = "neutral",
        output_dir: str = "./outputs/audio"
    ) -> str:
        """
        Generate speech from text

        Args:
            text: Text to synthesize
            request_id: Unique request identifier
            user_id: User identifier
            emotion: Emotion style (neutral, happy, sad, excited, etc.)
            output_dir: Output directory for audio files

        Returns:
            Path to generated audio file
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        audio_file = output_path / f"{request_id}.wav"

        if self.model_name == "cosyvoice3":
            await self._generate_cosyvoice(text, str(audio_file), emotion)
        elif self.model_name == "dia":
            await self._generate_dia(text, str(audio_file), emotion)
        else:
            raise ValueError(f"Unknown TTS model: {self.model_name}")

        logger.info(f"Generated audio: {audio_file}")
        return str(audio_file)

    async def _generate_cosyvoice(
        self,
        text: str,
        output_path: str,
        emotion: str = "neutral"
    ):
        """Generate using CosyVoice3 via HTTP API"""
        # CosyVoice3 API endpoint
        url = f"{self.cosyvoice_server}/inference_zero_shot"

        # Emotion mapping
        emotion_params = {
            "neutral": {"speed": 1.0, "pitch": 1.0},
            "happy": {"speed": 1.1, "pitch": 1.05},
            "sad": {"speed": 0.9, "pitch": 0.95},
            "excited": {"speed": 1.2, "pitch": 1.1},
            "calm": {"speed": 0.95, "pitch": 1.0}
        }.get(emotion, {"speed": 1.0, "pitch": 1.0})

        payload = {
            "tts_text": text,
            "prompt_text": "",  # Zero-shot mode
            "speed": emotion_params["speed"],
            "pitch": emotion_params["pitch"]
        }

        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()

            # Save audio
            with open(output_path, "wb") as f:
                f.write(response.content)

        except Exception as e:
            logger.error(f"CosyVoice generation failed: {e}")
            raise

    async def _generate_dia(
        self,
        text: str,
        output_path: str,
        emotion: str = "neutral"
    ):
        """Generate using Dia TTS"""
        # Dia API endpoint (adjust as needed)
        url = "http://localhost:8000/generate"

        payload = {
            "text": text,
            "voice": self.voice_id,
            "emotion": emotion
        }

        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()

            result = response.json()
            audio_data = base64.b64decode(result["audio"])

            with open(output_path, "wb") as f:
                f.write(audio_data)

        except Exception as e:
            logger.error(f"Dia generation failed: {e}")
            raise

    async def clone_voice(
        self,
        reference_audio: str,
        text: str,
        output_path: str
    ):
        """
        Clone voice from reference audio (CosyVoice3 feature)

        Args:
            reference_audio: Path to reference audio file
            text: Text to synthesize
            output_path: Output audio path
        """
        url = f"{self.cosyvoice_server}/inference_zero_shot"

        with open(reference_audio, "rb") as f:
            audio_data = f.read()

        files = {
            "prompt_wav": ("reference.wav", audio_data, "audio/wav")
        }
        data = {
            "tts_text": text,
            "prompt_text": ""  # Can add prompt text if available
        }

        try:
            response = await self._client.post(url, files=files, data=data)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(response.content)

        except Exception as e:
            logger.error(f"Voice cloning failed: {e}")
            raise

    async def close(self):
        """Close HTTP client"""
        await self._client.aclose()
