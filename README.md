# AI Girlfriend - Real-Time ComfyUI + WaveSpeed System

A high-performance real-time AI avatar generation system using ComfyUI with WaveSpeed optimizations for 24/7 deployment on RunPod.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Webcam    │  │   Chat UI   │  │ Voice Input │  │    OBS/RTMP Out     │ │
│  │  (OpenCV)   │  │  (React)    │  │  (Whisper)  │  │   (Streaming)       │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────────────────────┘ │
└─────────┼────────────────┼────────────────┼──────────────────────────────────┘
          │                │                │
          └────────────────┴────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────────────┐
│                           BACKEND LAYER (FastAPI)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Webcam    │  │    LLM      │  │   Prompt    │  │    Queue Manager    │ │
│  │   Capture   │→ │   (Ollama)  │→ │  Processor  │→ │   (ComfyUI API)     │ │
│  │  (Qwen VLM) │  │   + RAG     │  │             │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │ WebSocket API
┌──────────────────────────▼──────────────────────────────────────────────────┐
│                         COMFYUI LAYER (RunPod GPU)                           │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         IMAGE GENERATION                                │ │
│  │  Flux 1.1 + IP-Adapter + LoRA → WaveSpeed First Block Cache            │ │
│  │  Latency: ~2-3s | CFG: 3.5 | Steps: 6-8                                │ │
│  └───────────────────────────────┬─────────────────────────────────────────┘ │
│                                  │                                           │
│  ┌───────────────────────────────▼─────────────────────────────────────────┐ │
│  │                         VIDEO GENERATION                                │ │
│  │  Wan 2.2 I2V 720p → WaveSpeed Cache (0.15 strength)                    │ │
│  │  Latency: ~5-8s | 2-3s clips                                            │ │
│  └───────────────────────────────┬─────────────────────────────────────────┘ │
│                                  │                                           │
│  ┌───────────────────────────────▼─────────────────────────────────────────┐ │
│  │                      VOICE + LIPSYNC                                    │ │
│  │  CosyVoice3 TTS → Dia TTS → SadTalker Lip-Sync                         │ │
│  │  Latency: ~1-2s                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Performance Targets

| Component | Target Latency | Technology |
|-----------|---------------|------------|
| Chat Response | <1s | Ollama Llama 3.2 + RAG |
| Avatar Generation | 2-3s | Flux + WaveSpeed |
| Video Generation | 5-8s | Wan 2.2 I2V + WaveSpeed |
| Voice Synthesis | 1-2s | CosyVoice3 / Dia |
| Lip Sync | +1s | SadTalker |
| **Total Pipeline** | **<5s** | End-to-end |

## Speed Optimizations

### WaveSpeed First Block Cache
- **Speedup**: 50-60% faster generation
- **Usage**: Place before KSampler for Flux/Wan/LTXV
- **Image Gen**: 60s → 20s
- **Video Gen**: 15min → 8min

### TC (Tash) Cache Node
- **Speedup**: 50% across SDXL/Flux
- **Stackable**: Combine with WaveSpeed for 3x total gains

### Recommended Settings
```yaml
Flux Generation:
  cfg: 3.5
  steps: 6-8 (high stage)
  loras: false (initially)

Wan 2.2 I2V:
  cache_strength: 0.15  # Balanced motion/quality
  resolution: 720p
  frames: 24-48
```

## Project Structure

```
ai-girlfriend-comfyui/
├── workflows/           # ComfyUI workflow JSONs
│   ├── image-gen/      # Flux + IP-Adapter workflows
│   ├── video-gen/      # Wan 2.2 I2V workflows
│   ├── voice-lipsync/  # SadTalker + TTS workflows
│   └── full-pipeline/  # End-to-end integrated workflows
├── backend/            # FastAPI orchestration server
│   ├── api/           # REST endpoints
│   ├── core/          # Pipeline logic
│   └── utils/         # Helpers
├── deployment/        # Infrastructure configs
│   ├── docker/        # Container definitions
│   ├── runpod/        # RunPod templates
│   └── kubernetes/    # K8s manifests
├── configs/          # Model configs, prompts
├── models/           # Download scripts
├── scripts/          # Setup automation
└── docs/            # Documentation
```

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/dobrinsm/ai-girlfriend-comfyui.git
cd ai-girlfriend-comfyui
```

### 2. RunPod Deployment

See the [RunPod Getting Started Guide](docs/RUNPOD_GETTING_STARTED.md) for detailed instructions.

Quick deploy:
```bash
# Deploy to RunPod (RTX 4090 recommended)
cd deployment/runpod
./deploy.sh
```

### 3. Local Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
```

### 3. Run Workflows

```bash
# Queue a generation
python scripts/queue_generation.py --prompt "A friendly smile" --webcam-input
```

## Hardware Requirements

### Minimum (Development)
- GPU: RTX 3090 (24GB VRAM)
- RAM: 32GB
- Storage: 100GB SSD

### Recommended (Production)
- GPU: RTX 4090 (24GB VRAM) or A100 (40GB)
- RAM: 64GB
- Storage: 200GB NVMe SSD

## Model Downloads

See `models/download_models.sh` for automated model fetching:
- Flux 1.1 (dev/schnell)
- Wan 2.2 I2V
- IP-Adapter models
- LoRA weights
- CosyVoice3 / Dia TTS
- SadTalker checkpoints

## License

MIT License - See LICENSE file
