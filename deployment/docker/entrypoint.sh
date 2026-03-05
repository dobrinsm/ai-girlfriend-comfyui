#!/bin/bash
set -e

echo "========================================"
echo "AI Girlfriend - ComfyUI + WaveSpeed"
echo "========================================"

# Check GPU availability
if command -v nvidia-smi &> /dev/null; then
    echo "GPU Info:"
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
else
    echo "WARNING: nvidia-smi not found. GPU may not be available."
fi

# Set up model directories
mkdir -p /workspace/ComfyUI/models/{checkpoints,clip,controlnet,diffusers,embeddings,loras,upscale_models,vae,vae_approx,ipadapter,sadtalker}
mkdir -p /workspace/ComfyUI/output
mkdir -p /workspace/ComfyUI/input

# Create symlink for persistent network volume (RunPod)
if [ -d "/runpod-volume" ]; then
    echo "Setting up persistent volume..."

    # Models
    if [ ! -L "/workspace/ComfyUI/models/checkpoints" ] && [ -d "/runpod-volume/models/checkpoints" ]; then
        rm -rf /workspace/ComfyUI/models/checkpoints
        ln -s /runpod-volume/models/checkpoints /workspace/ComfyUI/models/checkpoints
    fi

    if [ ! -L "/workspace/ComfyUI/models/loras" ] && [ -d "/runpod-volume/models/loras" ]; then
        rm -rf /workspace/ComfyUI/models/loras
        ln -s /runpod-volume/models/loras /workspace/ComfyUI/models/loras
    fi

    if [ ! -L "/workspace/ComfyUI/models/ipadapter" ] && [ -d "/runpod-volume/models/ipadapter" ]; then
        rm -rf /workspace/ComfyUI/models/ipadapter
        ln -s /runpod-volume/models/ipadapter /workspace/ComfyUI/models/ipadapter
    fi

    # Output
    if [ ! -L "/workspace/ComfyUI/output" ] && [ -d "/runpod-volume/output" ]; then
        rm -rf /workspace/ComfyUI/output
        ln -s /runpod-volume/output /workspace/ComfyUI/output
    fi
fi

# Download models if specified
if [ "${DOWNLOAD_MODELS:-false}" = "true" ]; then
    echo "Downloading models..."
    python /workspace/ComfyUI/scripts/download_models.py
fi

# Start ComfyUI
echo "Starting ComfyUI..."
echo "Arguments: $@"

exec "$@"
