"""
Vision Language Model processor for webcam analysis
"""

import base64
import io
import logging
from pathlib import Path
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


class VLMProcessor:
    """Processes images using Qwen2-VL or similar VLM"""

    def __init__(self, model_name: str = "qwen2-vl-7b"):
        self.model_name = model_name
        self._model = None
        self._processor = None

    async def _load_model(self):
        """Lazy load the VLM model"""
        if self._model is None:
            try:
                from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
                import torch

                logger.info(f"Loading VLM model: {self.model_name}")

                self._processor = AutoProcessor.from_pretrained(
                    f"Qwen/{self.model_name}",
                    trust_remote_code=True
                )
                self._model = Qwen2VLForConditionalGeneration.from_pretrained(
                    f"Qwen/{self.model_name}",
                    torch_dtype=torch.float16,
                    device_map="auto",
                    trust_remote_code=True
                )

                logger.info("VLM model loaded successfully")

            except Exception as e:
                logger.error(f"Failed to load VLM model: {e}")
                raise

    async def analyze_frame(
        self,
        image_data: str,
        prompt: str = "Describe the person's mood, expression, and environment"
    ) -> str:
        """
        Analyze a webcam frame

        Args:
            image_data: Base64 encoded image or file path
            prompt: Analysis prompt

        Returns:
            Analysis text
        """
        await self._load_model()

        # Load image
        if image_data.startswith("data:image"):
            # Base64 encoded
            image_bytes = base64.b64decode(image_data.split(",")[-1])
            image = Image.open(io.BytesIO(image_bytes))
        elif Path(image_data).exists():
            image = Image.open(image_data)
        else:
            raise ValueError("Invalid image data")

        # Prepare inputs
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt}
                ]
            }
        ]

        text = self._processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._processor(
            text=[text],
            images=[image],
            return_tensors="pt"
        ).to(self._model.device)

        # Generate
        import torch
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=100,
                do_sample=False
            )

        response = self._processor.batch_decode(
            outputs[:, inputs.input_ids.shape[1]:],
            skip_special_tokens=True
        )[0]

        return response.strip()

    async def analyze_expression(self, image_data: str) -> dict:
        """
        Analyze facial expression specifically

        Returns:
            Dict with expression analysis
        """
        prompt = """Analyze the facial expression in this image. Provide:
1. Primary emotion (happy, sad, neutral, surprised, angry, fearful, disgusted)
2. Engagement level (0-10)
3. Brief description"""

        analysis = await self.analyze_frame(image_data, prompt)

        # Parse simple format
        lines = analysis.strip().split("\n")
        result = {
            "raw_analysis": analysis,
            "emotion": "neutral",
            "engagement": 5,
            "description": analysis
        }

        for line in lines:
            if "emotion" in line.lower():
                for emotion in ["happy", "sad", "neutral", "surprised", "angry", "fearful", "disgusted"]:
                    if emotion in line.lower():
                        result["emotion"] = emotion
                        break
            elif "engagement" in line.lower():
                try:
                    result["engagement"] = int(''.join(filter(str.isdigit, line)))
                except:
                    pass

        return result
