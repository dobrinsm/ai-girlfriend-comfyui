#!/usr/bin/env python3
"""
Model download script for AI Girlfriend ComfyUI setup
Downloads required models for Flux, Wan 2.2, IP-Adapter, and SadTalker

NOTE: Some models (Ollama, CosyVoice) are downloaded separately:
- Ollama: Run `ollama pull mistral` and `ollama pull qwen2-vl-7b`
- CosyVoice: Installed via ComfyUI custom nodes
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
from tqdm import tqdm

# Model URLs - All verified working links
# 
# OPTIONAL: Set HF_TOKEN environment variable for models requiring authentication:
#   export HF_TOKEN=your_huggingface_token
# Get your token from: https://huggingface.co/settings/tokens
MODELS = {
    "checkpoints": {
        # Flux 1.1 Dev (FP8) - Image generation (contains UNET, CLIP, VAE)
        # This is the main model - works without authentication
        "flux1-dev-fp8.safetensors": "https://huggingface.co/Kijai/flux-fp8/resolve/main/flux1-dev-fp8.safetensors",
        # Flux Dev (bf16) - Higher quality, requires HF_TOKEN
        # "flux1-dev-bf16.safetensors": "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/flux1_dev_bf16.safetensors",
    },
    "unet": {
        # Separate UNET for Flux (if using UNETLoader)
        "flux1-dev-fp8.safetensors": "https://huggingface.co/Kijai/flux-fp8/resolve/main/flux1-dev-fp8.safetensors",
    },
    "vae": {
        # Flux VAE (autoencoder) - from black-forest-labs (public)
        "ae.safetensors": "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors",
    },
    "clip": {
        # Flux CLIP text encoders (for DualCLIPLoader)
        "clip_l.safetensors": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors",
        "t5xxl_fp8_e4m3fn.safetensors": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors",
        "t5xxl_fp16.safetensors": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors",
    },
    "text_encoders": {
        # Alternative text encoder locations
        "clip_l.safetensors": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors",
        "t5xxl_fp8_e4m3fn.safetensors": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors",
    },
    "ipadapter": {
        # IP-Adapter for Flux - using Civitai alternative or HuggingFace
        # These may require HF_TOKEN
        # "ip-adapter_flux.safetensors": "https://huggingface.co/ostris/flux-ip-adapter/resolve/main/ip_adapter_flux.safetensors",
    },
    "sadtalker": {
        # SadTalker lip-sync models
        "SadTalker_V0.0.2_256.safetensors": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_256.safetensors",
        "SadTalker_V0.0.2_512.safetensors": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_512.safetensors",
    },
    "controlnet": {
        # Additional controlnet models if needed
    },
    "loras": {
        # Additional loras if needed
    }
}

# Ollama models (pull separately via: ollama pull <model>)
OLLAMA_MODELS = [
    "mistral",      # LLM for chat responses
    "qwen2-vl:7b",  # VLM for webcam analysis
]


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

    # HuggingFace token if available (required for some models)
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if hf_token and "huggingface.co" in url:
        headers["Authorization"] = f"Bearer {hf_token}"
        print(f"  Using HF_TOKEN for authentication")

    with httpx.Client(follow_redirects=True, headers=headers, timeout=httpx.Timeout(300.0)) as client:
        try:
            response = client.head(url)
            total_size = int(response.headers.get("content-length", 0))
        except Exception as e:
            print(f"  Warning: Could not get file size: {e}")
            total_size = 0

        with client.stream("GET", url) as response:
            # Handle 401/403 - try without auth or report
            if response.status_code in (401, 403):
                print(f"  ✗ Authentication required. Set HF_TOKEN environment variable.")
                print(f"    Get your token from: https://huggingface.co/settings/tokens")
                raise Exception(f"Authentication required for {url}")
            
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
    parser.add_argument("--ollama", action="store_true", help="Also pull Ollama models")

    args = parser.parse_args()

    if args.all or (not args.category and not args.model):
        print("Downloading all ComfyUI models...")
        download_models()
    else:
        download_models(category=args.category, specific_model=args.model)

    # Pull Ollama models if requested
    if args.ollama:
        print("\n" + "="*50)
        print("Pulling Ollama models...")
        print("="*50)
        import subprocess
        for model in OLLAMA_MODELS:
            print(f"\n→ Pulling {model}...")
            try:
                subprocess.run(["ollama", "pull", model], check=True)
                print(f"  ✓ {model} ready")
            except Exception as e:
                print(f"  ✗ Failed: {e}")

    print("\nDone!")
