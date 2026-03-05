#!/usr/bin/env python3
"""
Model download script for AI Girlfriend ComfyUI setup
Downloads required models for Flux, Wan 2.2, IP-Adapter, and SadTalker
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
from tqdm import tqdm

# Model URLs
MODELS = {
    "checkpoints": {
        # Flux models
        "flux1-dev-fp8.safetensors": "https://huggingface.co/Kijai/flux-fp8/resolve/main/flux1-dev-fp8.safetensors",
        "flux1-schnell-fp8.safetensors": "https://huggingface.co/Kijai/flux-fp8/resolve/main/flux1-schnell-fp8.safetensors",

        # Wan 2.2 models
        "wan2.2_i2v_720p_fp8.safetensors": "https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-720P/resolve/main/wan2.1_i2v_720p_fp8.safetensors",
        "wan2.2_i2v_480p_fp8.safetensors": "https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-480P/resolve/main/wan2.1_i2v_480p_fp8.safetensors",
    },
    "vae": {
        "ae.safetensors": "https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors",
    },
    "clip": {
        "clip_l.safetensors": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors",
        "t5xxl_fp8_e4m3fn.safetensors": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors",
    },
    "ipadapter": {
        "ip-adapter_flux.1-schnell": "https://huggingface.co/XLabs-AI/flux-ip-adapter/resolve/main/ip_adapter.safetensors",
    },
    "sadtalker": {
        "SadTalker_V0.0.2_256.safetensors": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_256.safetensors",
        "SadTalker_V0.0.2_512.safetensors": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_512.safetensors",
    }
}


def get_model_dir() -> Path:
    """Get the models directory"""
    # Check for RunPod volume first
    runpod_volume = Path("/runpod-volume/models")
    if runpod_volume.exists():
        return runpod_volume

    # Default ComfyUI models directory
    comfy_models = Path("/workspace/ComfyUI/models")
    if comfy_models.exists():
        return comfy_models

    # Local development
    local_models = Path("./models")
    local_models.mkdir(parents=True, exist_ok=True)
    return local_models


def download_file(url: str, dest_path: Path, chunk_size: int = 8192):
    """Download a file with progress bar"""
    headers = {}

    # HuggingFace token if available
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token and "huggingface.co" in url:
        headers["Authorization"] = f"Bearer {hf_token}"

    with httpx.Client(follow_redirects=True, headers=headers) as client:
        response = client.head(url)
        total_size = int(response.headers.get("content-length", 0))

        with client.stream("GET", url) as response:
            response.raise_for_status()

            with open(dest_path, "wb") as f:
                with tqdm(
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    desc=dest_path.name
                ) as pbar:
                    for chunk in response.iter_bytes(chunk_size=chunk_size):
                        f.write(chunk)
                        pbar.update(len(chunk))


def download_models(category: str = None, specific_model: str = None):
    """Download models"""
    model_dir = get_model_dir()

    categories = [category] if category else MODELS.keys()

    for cat in categories:
        if cat not in MODELS:
            print(f"Unknown category: {cat}")
            continue

        cat_dir = model_dir / cat
        cat_dir.mkdir(parents=True, exist_ok=True)

        print(f"\nDownloading {cat} models to {cat_dir}")

        for model_name, url in MODELS[cat].items():
            if specific_model and model_name != specific_model:
                continue

            dest_path = cat_dir / model_name

            if dest_path.exists():
                print(f"  ✓ {model_name} already exists")
                continue

            print(f"  ↓ Downloading {model_name}...")
            try:
                download_file(url, dest_path)
                print(f"  ✓ Downloaded {model_name}")
            except Exception as e:
                print(f"  ✗ Failed to download {model_name}: {e}")

                # Clean up partial download
                if dest_path.exists():
                    dest_path.unlink()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download AI Girlfriend models")
    parser.add_argument("--category", help="Model category to download")
    parser.add_argument("--model", help="Specific model to download")
    parser.add_argument("--all", action="store_true", help="Download all models")

    args = parser.parse_args()

    if args.all or (not args.category and not args.model):
        print("Downloading all models...")
        download_models()
    else:
        download_models(category=args.category, specific_model=args.model)

    print("\nDone!")
