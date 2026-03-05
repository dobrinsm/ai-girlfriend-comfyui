# AI Girlfriend - Setup Guide

Complete setup guide for the ComfyUI + WaveSpeed real-time AI generation system.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Local Development](#local-development)
3. [RunPod Deployment](#runpod-deployment)
4. [Model Downloads](#model-downloads)
5. [Configuration](#configuration)
6. [Troubleshooting](#troubleshooting)

## Quick Start

### Prerequisites

- **GPU**: NVIDIA GPU with 24GB+ VRAM (RTX 3090/4090 recommended)
- **RAM**: 32GB+ system memory
- **Storage**: 100GB+ free space
- **OS**: Ubuntu 22.04 or Windows with WSL2

### 1. Clone and Setup

```bash
git clone https://github.com/dobrinsm/ai-girlfriend-comfyui.git
cd ai-girlfriend-comfyui

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install backend dependencies
cd backend
pip install -r requirements.txt
```

### 2. Install ComfyUI

```bash
# Clone ComfyUI
cd ..
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
pip install -r requirements.txt

# Install custom nodes
mkdir -p custom_nodes
cd custom_nodes

# WaveSpeed (essential for speed)
git clone https://github.com/chengzeyi/Comfy-WaveSpeed.git

# ComfyUI Manager
git clone https://github.com/ltdrdata/ComfyUI-Manager.git

# Video Helper Suite
git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git

# IP-Adapter Plus
git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git

# SadTalker
git clone https://github.com/OpenTalker/SadTalker.git

# Install dependencies for all custom nodes
for dir in */; do
    if [ -f "$dir/requirements.txt" ]; then
        pip install -r "$dir/requirements.txt"
    fi
done
```

### 3. Download Models

```bash
cd ../..
python scripts/download_models.py --all
```

Or download manually:

| Model | Size | URL | Destination |
|-------|------|-----|-------------|
| Flux 1.1 Dev FP8 | ~17GB | [HuggingFace](https://huggingface.co/Kijai/flux-fp8) | `models/checkpoints/` |
| Wan 2.2 I2V 720p | ~30GB | [HuggingFace](https://huggingface.co/Wan-AI) | `models/checkpoints/` |
| IP-Adapter Flux | ~1GB | [HuggingFace](https://huggingface.co/XLabs-AI/flux-ip-adapter) | `models/ipadapter/` |
| Qwen2-VL | ~15GB | [HuggingFace](https://huggingface.co/Qwen/Qwen2-VL-7B) | Auto-downloaded |

### 4. Start Services

Terminal 1 - ComfyUI:
```bash
cd ComfyUI
python main.py --listen 0.0.0.0 --port 8188 --preview-method auto
```

Terminal 2 - Backend:
```bash
cd backend
cp .env.example .env
# Edit .env with your settings
python main.py
```

### 5. Test

```bash
# Health check
curl http://localhost:8000/health

# Generate avatar
curl -X POST "http://localhost:8000/api/v1/generate/avatar" \
  -F "prompt=beautiful female avatar, friendly smile" \
  -F "user_id=test_user"
```

## Local Development

### Backend Development

```bash
cd backend

# Install dev dependencies
pip install pytest pytest-asyncio black isort mypy

# Run tests
pytest

# Format code
black .
isort .

# Type checking
mypy .

# Run with auto-reload
python main.py --reload
```

### ComfyUI Workflow Development

1. Open ComfyUI at `http://localhost:8188`
2. Load workflows from `workflows/` directory
3. Modify and save new versions
4. Export as API format for backend integration

### Adding Custom Nodes

```bash
cd ComfyUI/custom_nodes

# Example: Add WAS Node Suite
git clone https://github.com/WASasquatch/was-node-suite-comfyui.git
cd was-node-suite-comfyui
pip install -r requirements.txt
```

## RunPod Deployment

### Option 1: Using Deploy Script

```bash
cd deployment/runpod
./deploy.sh
```

### Option 2: Manual Deployment

1. **Build Docker Image**:
```bash
cd deployment/docker
docker build -t ai-girlfriend-comfyui:latest -f Dockerfile.comfyui .
```

2. **Push to Registry** (optional):
```bash
docker tag ai-girlfriend-comfyui:latest your-registry/ai-girlfriend-comfyui:latest
docker push your-registry/ai-girlfriend-comfyui:latest
```

3. **Deploy on RunPod**:
   - Go to [RunPod Console](https://www.runpod.io/console/pods)
   - Click "Deploy"
   - Select "Custom Template"
   - Upload `deployment/runpod/pod-template.json`
   - Configure network volume (100GB recommended)
   - Deploy with RTX 4090

### Persistent Storage Setup

```bash
# On RunPod pod, models are stored in /runpod-volume
# Create symlinks for persistence

mkdir -p /runpod-volume/models/{checkpoints,loras,ipadapter}
mkdir -p /runpod-volume/output

# The entrypoint.sh script handles symlinks automatically
```

## Model Downloads

### Automated Download

```bash
# Download all models
python scripts/download_models.py --all

# Download specific category
python scripts/download_models.py --category checkpoints

# Download specific model
python scripts/download_models.py --model flux1-dev-fp8.safetensors
```

### Manual Download

#### Required Models

**Flux 1.1 (Image Generation)**
```bash
# FP8 version (recommended for speed)
wget https://huggingface.co/Kijai/flux-fp8/resolve/main/flux1-dev-fp8.safetensors \
  -O ComfyUI/models/checkpoints/flux1-dev-fp8.safetensors

# Text encoders
wget https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors \
  -O ComfyUI/models/clip/clip_l.safetensors

wget https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors \
  -O ComfyUI/models/clip/t5xxl_fp8_e4m3fn.safetensors

# VAE
wget https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors \
  -O ComfyUI/models/vae/ae.safetensors
```

**Wan 2.2 (Video Generation)**
```bash
# I2V 720p model
wget https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-720P/resolve/main/wan2.1_i2v_720p_fp8.safetensors \
  -O ComfyUI/models/checkpoints/wan2.2_i2v_720p_fp8.safetensors
```

**IP-Adapter (Face Consistency)**
```bash
wget https://huggingface.co/XLabs-AI/flux-ip-adapter/resolve/main/ip_adapter.safetensors \
  -O ComfyUI/models/ipadapter/ip-adapter_flux.1-schnell.safetensors
```

**SadTalker (Lip Sync)**
```bash
wget https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_256.safetensors \
  -O ComfyUI/models/sadtalker/SadTalker_V0.0.2_256.safetensors
```

## Configuration

### ComfyUI Settings

Edit `configs/comfyui.yaml`:

```yaml
# Enable WaveSpeed cache
wavespeed:
  enabled: true
  first_block_cache: true
  cache_strength: 0.15  # Adjust 0.0-1.0

# Memory management
reserve_vram: 2  # Reserve 2GB for other processes
```

### Backend Settings

Create `backend/.env`:

```bash
# Copy example
cp backend/.env.example backend/.env

# Edit with your settings
DEBUG=false
COMFYUI_URL=http://localhost:8188
LLM_MODEL=llama3.2:7b
TTS_MODEL=cosyvoice3
```

### WaveSpeed Optimization

For different use cases:

| Use Case | Cache Strength | Speed | Quality |
|----------|---------------|-------|---------|
| Real-time chat | 0.20 | Fastest | Good |
| Balanced | 0.15 | Fast | Better |
| High quality | 0.10 | Medium | Best |

## Troubleshooting

### Common Issues

**1. CUDA Out of Memory**
```bash
# Reduce batch size or resolution
# Enable CPU offloading in ComfyUI
# Increase reserve_vram in config
```

**2. WaveSpeed Not Working**
```bash
# Check Triton installation
pip install triton

# Verify WaveSpeed nodes are installed
ls ComfyUI/custom_nodes/Comfy-WaveSpeed
```

**3. Models Not Loading**
```bash
# Check model paths
python scripts/download_models.py --category checkpoints

# Verify file integrity
ls -lh ComfyUI/models/checkpoints/
```

**4. Slow Generation**
```bash
# Check GPU utilization
nvidia-smi

# Enable FP8 if supported
# Verify WaveSpeed is enabled
# Check cache strength setting
```

**5. WebSocket Connection Failed**
```bash
# Check ComfyUI is running
curl http://localhost:8188/system_stats

# Verify port in .env matches ComfyUI port
```

### Performance Tuning

**For RTX 4090 (24GB)**:
```yaml
# Maximum performance
wavespeed:
  cache_strength: 0.15

# Use FP8 models
# Batch size: 1
# Resolution: 768x1344 (Flux), 1280x720 (Wan)
```

**For RTX 3090 (24GB)**:
```yaml
# Balanced settings
wavespeed:
  cache_strength: 0.20

# May need to reduce resolution slightly
# Enable xformers attention
```

### Getting Help

- **ComfyUI Issues**: [ComfyUI GitHub](https://github.com/comfyanonymous/ComfyUI)
- **WaveSpeed Issues**: [WaveSpeed GitHub](https://github.com/chengzeyi/Comfy-WaveSpeed)
- **RunPod Support**: [RunPod Docs](https://docs.runpod.io/)
