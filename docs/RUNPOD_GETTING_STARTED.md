# RunPod Getting Started Guide

Step-by-step guide to deploy the AI Girlfriend system on RunPod.

## Overview

You'll need to rent:
1. **Network Volume** (Persistent Storage) - For models (~100GB)
2. **GPU Pod** (RTX 4090) - For running ComfyUI + Backend

## Step 1: Create Network Volume (Storage)

This is where all your models will be stored permanently.

1. Go to [RunPod Console](https://www.runpod.io/console/user/storage)
2. Click **"Network Volumes"** → **"Create Volume"**
3. Configure:
   - **Name**: `ai-girlfriend-models`
   - **Size**: `100 GB` (minimum, can expand later)
   - **Data Center**: Choose closest to you (e.g., `US-East` or `EU-Amsterdam`)
4. Click **"Create"**

**Cost**: ~$0.10/GB/month = ~$10/month for 100GB

## Step 2: Deploy GPU Pod

### Option A: Using RunPod Web GUI (Recommended for Beginners)

1. Go to [RunPod Console](https://www.runpod.io/console/pods)
2. Click **"Deploy"**
3. Select **"GPU"** tab
4. Choose **"RTX 4090"** (or RTX 3090 if 4090 unavailable)
5. Configure Template:
   - Click **"Custom Template"**
   - **Container Image**: `pytorch/pytorch:2.5.1-cuda12.1-cudnn8-runtime`
   - Or use: `runpod/pytorch:2.5.1-py3.11-cuda12.1-devel-ubuntu22.04`

6. **Environment Variables** (click "Add Environment Variable"):
   ```
   PYTHONUNBUFFERED=1
   DOWNLOAD_MODELS=true
   WAVESPEED_CACHE=true
   WAVESPEED_CACHE_STRENGTH=0.15
   ```

7. **Volume Mount** (Important!):
   - Under "Network Volume", select your `ai-girlfriend-models` volume
   - **Container Mount Path**: `/runpod-volume`

8. **Ports**:
   - Add port `8188` (ComfyUI)
   - Add port `8000` (Backend API)
   - Add port `22` (SSH)

9. Click **"Deploy"**

**Cost**: ~$0.44-$0.69/hour for RTX 4090

### Option B: Using RunPod CLI (Advanced)

```bash
# Install runpodctl (Go binary - NOT a pip package)
# Linux/macOS:
wget -qO /usr/local/bin/runpodctl https://github.com/runpod/runpodctl/releases/latest/download/runpodctl-linux-amd64
chmod +x /usr/local/bin/runpodctl
# Or via Homebrew on macOS:
# brew install runpod/runpodctl/runpodctl

# Login
runpodctl config --apiKey YOUR_API_KEY

# Create network volume
runpodctl create volume \
  --name ai-girlfriend-models \
  --size 100 \
  --dataCenterId US-OR-1

# Deploy pod
runpodctl create pod \
  --name ai-girlfriend \
  --gpuType "NVIDIA RTX 4090" \
  --imageName "pytorch/pytorch:2.5.1-cuda12.1-cudnn8-runtime" \
  --volumeSize 100 \
  --containerDiskSize 50 \
  --ports "8188:8188,8000:8000,22:22" \
  --env "DOWNLOAD_MODELS=true" \
  --env "WAVESPEED_CACHE=true"
```

## Step 3: Connect to Your Pod

Once the pod is running (status shows "Running"):

### Method 1: Web Terminal (Easiest)

1. Click on your pod in the console
2. Click **"Connect"** → **"Web Terminal"**
3. A terminal opens in your browser

### Method 2: SSH (Recommended)

1. Click on your pod → **"Connect"** → **"SSH"**
2. Copy the SSH command, example:
   ```bash
   ssh root@123.45.67.89 -p 12345
   ```
3. Run in your local terminal

### Method 3: VS Code Remote (Best for Development)

1. Install "Remote - SSH" extension in VS Code
2. Add to `~/.ssh/config`:
   ```
   Host runpod-ai-girlfriend
       HostName 123.45.67.89
       User root
       Port 12345
       StrictHostKeyChecking no
   ```
3. Connect via VS Code Remote Explorer

## Step 4: Setup Inside the Pod

Once connected to your pod:

### 4.1 Initial Setup

```bash
# Update system
apt-get update && apt-get install -y git wget curl vim

# Install Python dependencies
pip install --upgrade pip

# Install ComfyUI dependencies
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r https://raw.githubusercontent.com/comfyanonymous/ComfyUI/master/requirements.txt

# Install Triton for WaveSpeed
pip install triton
```

### 4.2 Clone and Setup Project

```bash
# Go to persistent volume (models stored here)
cd /runpod-volume

# Clone the project
git clone https://github.com/dobrinsm/ai-girlfriend-comfyui.git ai-girlfriend-comfyui
cd ai-girlfriend-comfyui

# Create model directories
mkdir -p /runpod-volume/models/{checkpoints,clip,vae,loras,ipadapter,sadtalker}

# Download models
python scripts/download_models.py --all
```

### 4.3 Install ComfyUI

```bash
# Clone ComfyUI
cd /workspace  # or /runpod-volume for persistence
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
pip install -r requirements.txt

# Install custom nodes
mkdir -p custom_nodes
cd custom_nodes

git clone https://github.com/chengzeyi/Comfy-WaveSpeed.git
git clone https://github.com/ltdrdata/ComfyUI-Manager.git
git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git
git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git
git clone https://github.com/OpenTalker/SadTalker.git

# Install dependencies for custom nodes
for dir in */; do
    if [ -f "$dir/requirements.txt" ]; then
        pip install -r "$dir/requirements.txt"
    fi
done
```

### 4.4 Setup Backend

```bash
cd /runpod-volume/ai-girlfriend-comfyui/backend

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << 'EOF'
DEBUG=false
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
COMFYUI_URL=http://localhost:8188
COMFYUI_WS_URL=ws://localhost:8188/ws
WORKFLOW_DIR=/runpod-volume/ai-girlfriend-comfyui/workflows
OUTPUT_DIR=/runpod-volume/outputs
VLM_MODEL=qwen2-vl-7b
LLM_MODEL=llama3.2:7b
TTS_MODEL=cosyvoice3
TTS_VOICE_ID=friendly_female
MEMORY_DB_PATH=/runpod-volume/data/memory.db
MAX_MEMORY_ITEMS=50
DEFAULT_CFG=3.5
DEFAULT_STEPS=6
WAVESPEED_CACHE=true
CACHE_STRENGTH=0.15
MAX_CONCURRENT_GENERATIONS=2
REQUEST_TIMEOUT=300
EOF
```

### 4.5 Start Services

**Terminal 1 - Start ComfyUI:**
```bash
cd /workspace/ComfyUI
python main.py --listen 0.0.0.0 --port 8188 --preview-method auto
```

**Terminal 2 - Start Backend:**
```bash
cd /runpod-volume/ai-girlfriend-comfyui/backend
python main.py
```

**Terminal 3 - Install Ollama (for LLM):**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull model
ollama pull llama3.2:7b

# Start Ollama server
ollama serve
```

## Step 5: Access Your Services

Once everything is running:

| Service | URL | Access |
|---------|-----|--------|
| ComfyUI | `http://<pod-ip>:8188` | Open in browser |
| Backend API | `http://<pod-ip>:8000` | API endpoint |
| API Docs | `http://<pod-ip>:8000/docs` | Swagger UI |

**Find your pod IP:**
- In RunPod console, click on your pod
- Look for "Public IP" or use the "Connect" button

## Step 6: Test the System

From your local machine:

```bash
# Test health
curl http://<pod-ip>:8000/health

# Generate avatar
curl -X POST "http://<pod-ip>:8000/api/v1/generate/avatar" \
  -F "prompt=beautiful female avatar, friendly smile" \
  -F "user_id=test_user"

# Or use the helper script
python scripts/queue_generation.py \
  --api-url http://<pod-ip>:8000 \
  --type chat \
  --text "Hello! How are you?"
```

## Step 7: Persistent Setup (Important!)

To avoid losing work when pod stops:

### 7.1 Create Startup Script

```bash
cat > /runpod-volume/start.sh << 'EOF'
#!/bin/bash

echo "Starting AI Girlfriend System..."

# Start ComfyUI
cd /workspace/ComfyUI
python main.py --listen 0.0.0.0 --port 8188 --preview-method auto &

# Wait for ComfyUI
sleep 10

# Start Backend
cd /runpod-volume/ai-girlfriend-comfyui/backend
python main.py &

# Start Ollama
ollama serve &

echo "All services started!"
echo "ComfyUI: http://localhost:8188"
echo "Backend: http://localhost:8000"

# Keep script running
tail -f /dev/null
EOF

chmod +x /runpod-volume/start.sh
```

### 7.2 Save Model Checkpoints

Models in `/runpod-volume/models/` are persisted. Always store models there, not in `/workspace`.

## Cost Estimation

| Component | Cost | Notes |
|-----------|------|-------|
| Network Volume (100GB) | ~$10/month | Persistent storage |
| RTX 4090 Pod | ~$0.50/hour | Only when running |
| **Daily usage (4 hours)** | ~$2/day | ~$60/month |
| **Daily usage (8 hours)** | ~$4/day | ~$120/month |

## Stopping vs Terminating

- **Stop Pod**: Keeps your setup, stops billing for GPU. Volume persists.
- **Terminate Pod**: Deletes everything except network volume. You lose the pod setup but keep models.

**Recommendation**: Always use "Stop" unless you want to completely reset.

## Troubleshooting

### Pod Won't Start
- Check GPU availability in your selected data center
- Try a different data center
- Reduce container disk size to 20GB

### Out of Memory
- Close ComfyUI preview: `--preview-method none`
- Enable CPU offload in ComfyUI settings
- Reduce batch size in workflows

### Models Not Found
- Ensure models are in `/runpod-volume/models/`
- Check symlinks: `ls -la /workspace/ComfyUI/models/`
- Re-run download script

### Can't Connect to Services
- Check firewall rules in RunPod
- Verify ports are exposed: `netstat -tlnp`
- Check service logs for errors

## Next Steps

1. **Upload Custom LoRAs**: Place in `/runpod-volume/models/loras/`
2. **Configure Workflows**: Edit in ComfyUI and save to `/runpod-volume/ai-girlfriend-comfyui/workflows/`
3. **Set up Domain**: Use Cloudflare tunnel or RunPod serverless for public access
4. **Monitor Costs**: Set up billing alerts in RunPod console

## Quick Reference Commands

```bash
# Check GPU
nvidia-smi

# Check disk space
df -h

# Check memory
free -h

# View logs
tail -f /workspace/ComfyUI/comfyui.log

# Restart ComfyUI
pkill -f "python main.py"
cd /workspace/ComfyUI && python main.py --listen 0.0.0.0 --port 8188

# Update ComfyUI
cd /workspace/ComfyUI && git pull

# Update custom nodes
cd /workspace/ComfyUI/custom_nodes
for dir in */; do cd "$dir" && git pull && cd ..; done
```
