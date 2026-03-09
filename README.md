# AI Girlfriend - Real-Time ComfyUI + WaveSpeed System

A high-performance real-time AI avatar generation system using ComfyUI with WaveSpeed optimizations. Creates AI avatar images, videos with lip-syncing, and voice responses.

## What It Does

```
User Message → LLM (Ollama) → Response + Avatar (Flux) → Video (Wan 2.2) → Lip-Sync (SadTalker) + Voice (CosyVoice)
```

| Component | Model | Latency |
|-----------|-------|---------|
| Chat Response | Llama 3.2 (Ollama) | <1s |
| Avatar Image | Flux 1.1 FP8 | ~2-3s |
| Video Generation | Wan 2.2 I2V | ~5-8s |
| Voice Synthesis | CosyVoice3 | ~1-2s |
| Lip Sync | SadTalker | ~1s |

## Quick Start (RunPod - No Network Volume Required)

### Step 1: Deploy GPU Pod on RunPod

1. Go to [RunPod Console](https://www.runpod.io/console/pods)
2. Click **Deploy**
3. Select the **GPU** tab
4. Choose **RTX 4090** (or RTX 3090 if unavailable)
5. Under "Container Image", select **PyTorch** (or enter `runpod/pytorch:2.1.0-cu118-ubuntu22.04`)
6. Set **Container Disk Size** to **150 GB** (required for models)
7. In "Expose HTTP Ports", enter: `8188,8000,3000` (comma-separated)

### Step 2: Run One-Click Setup

SSH into your pod and run:

```bash
curl -fsSL https://raw.githubusercontent.com/dobrinsm/ai-girlfriend-comfyui/main/scripts/setup_runpod.sh | bash
```

Or if you already have the repo cloned:

```bash
cd /workspace
git clone https://github.com/dobrinsm/ai-girlfriend-comfyui.git
cd ai-girlfriend-comfyui
bash scripts/setup_runpod.sh
```

### Step 3: Access Services

Find your Pod ID in RunPod Console → Connect, then use:

| Service | URL |
|---------|-----|
| Frontend | `https://<pod-id>-3000.proxy.runpod.net` |
| ComfyUI | `https://<pod-id>-8188.proxy.runpod.net` |
| Backend API | `https://<pod-id>-8000.proxy.runpod.net` |
| API Docs | `https://<pod-id>-8000.proxy.runpod.net/docs` |

**Note:** The frontend will automatically detect the backend. If it doesn't connect, try:
`https://<pod-id>-3000.proxy.runpod.net?backend=https://<pod-id>-8000.proxy.runpod.net`

## Hardware Requirements

| Spec | Minimum | Recommended |
|------|---------|------------|
| GPU | RTX 3090 (24GB) | RTX 4090 (24GB) |
| VRAM | 20GB | 24GB |
| Disk | 100GB | 200GB |
| RAM | 32GB | 64GB |

## Services Started

The setup script automatically starts:

1. **Frontend** (port 3000) - Web UI
2. **ComfyUI** (port 8188) - Image/Video generation
3. **Backend API** (port 8000) - FastAPI orchestration
4. **Ollama** (port 11434) - LLM for chat
5. **CosyVoice** (port 50000) - Text-to-Speech

## Project Structure

```
ai-girlfriend-comfyui/
├── backend/              # FastAPI server
│   ├── main.py         # API entry point
│   ├── core/           # Pipeline logic
│   └── requirements.txt
├── scripts/
│   ├── setup_runpod.sh  # One-click setup (USE THIS)
│   └── download_models.py
├── workflows/           # ComfyUI workflows
│   ├── image-gen/     # Flux workflows
│   ├── video-gen/     # Wan 2.2 workflows
│   └── full-pipeline/
└── configs/            # Configuration
```

## Usage

### Generate Avatar

```bash
curl -X POST "https://<pod-id>-8000.proxy.runpod.net/api/v1/generate/avatar" \
  -F "prompt=beautiful female avatar, friendly smile" \
  -F "user_id=test_user"
```

### Chat

```bash
# WebSocket chat
python scripts/queue_generation.py \
  --ws-url wss://<pod-id>-8000.proxy.runpod.net \
  --type chat \
  --text "Hello!"
```

## Troubleshooting

### Services Not Starting

```bash
# Check logs
tail -f /workspace/logs/comfyui.log
tail -f /workspace/logs/backend.log

# Restart services
bash /workspace/start_ai_girlfriend.sh
```

### Out of Memory

- Stop other processes
- Use smaller models (Flux schnell instead of dev)
- Reduce workflow resolution

### Can't Access Services

- Verify ports are exposed in RunPod template
- Use the proxy URL, not direct IP:port
- Check pod is running (not stopped)

## Cost

- RTX 4090: ~$0.44-0.69/hour
- Pod storage (150GB): Included in disk size

## License

MIT License
