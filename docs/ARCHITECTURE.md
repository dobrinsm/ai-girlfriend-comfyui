# AI Girlfriend - Architecture Documentation

## System Overview

The AI Girlfriend system is a real-time multimodal AI avatar generation platform built on ComfyUI with WaveSpeed optimizations. It combines state-of-the-art models for image generation, video animation, voice synthesis, and lip-syncing to create a responsive AI companion.

## Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  Webcam Input    │  Chat Interface    │  Voice Input    │  Streaming Out   │
│  (OpenCV)        │  (WebSocket)       │  (Whisper)      │  (WebRTC/RTMP)   │
└──────────────────┴────────────────────┴─────────────────┴──────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND LAYER (FastAPI)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Webcam    │  │    LLM      │  │   Pipeline  │  │    Queue Manager    │ │
│  │   Capture   │→ │   (Ollama)  │→ │   Manager   │→ │   (ComfyUI API)     │ │
│  │  (Qwen VLM) │  │   + RAG     │  │             │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│         │                │                │                │                 │
│         └────────────────┴────────────────┴────────────────┘                 │
│                                    │                                         │
│  ┌─────────────────────────────────▼──────────────────────────────────────┐  │
│  │                         Memory Manager (SQLite)                        │  │
│  │              Conversation history, user preferences                     │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │ WebSocket API
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMFYUI LAYER (GPU Server)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  1. IMAGE GENERATION (Flux 1.1 + IP-Adapter + WaveSpeed Cache)         │ │
│  │     - Input: Text prompt + optional webcam image                       │ │
│  │     - Output: 768x1344 avatar image                                    │ │
│  │     - Latency: ~2-3s                                                   │ │
│  │     - Settings: CFG 3.5, 6-8 steps, FP8 precision                      │ │
│  └───────────────────────────────┬─────────────────────────────────────────┘ │
│                                  │                                           │
│  ┌───────────────────────────────▼─────────────────────────────────────────┐ │
│  │  2. VIDEO GENERATION (Wan 2.2 I2V + WaveSpeed Cache)                   │ │
│  │     - Input: Avatar image + motion prompt                              │ │
│  │     - Output: 1280x720 video, 24-48 frames                             │ │
│  │     - Latency: ~5-8s                                                   │ │
│  │     - Settings: Cache strength 0.15, 6 steps                           │ │
│  └───────────────────────────────┬─────────────────────────────────────────┘ │
│                                  │                                           │
│  ┌───────────────────────────────▼─────────────────────────────────────────┐ │
│  │  3. VOICE + LIPSYNC (CosyVoice3 + SadTalker)                           │ │
│  │     - Input: Text response + avatar image                              │ │
│  │     - Output: Lip-synced video with audio                              │ │
│  │     - Latency: ~1-2s (TTS) + ~1s (lip-sync)                            │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Chat Message Flow

```
1. User sends message
   │
   ▼
2. Webcam frame captured (optional)
   │
   ▼
3. VLM analyzes frame → visual context
   │
   ▼
4. LLM generates response (with RAG memory)
   │
   ▼
5. Parallel generation:
   ├── TTS → audio file
   ├── Flux → avatar image
   │
   ▼
6. Wan 2.2 → video from avatar
   │
   ▼
7. SadTalker → lip-sync video
   │
   ▼
8. Stream to client
```

### Performance Budget

| Stage | Target | Model | Optimization |
|-------|--------|-------|--------------|
| VLM Analysis | <500ms | Qwen2-VL-7B | INT8 quantization |
| LLM Response | <1s | Llama 3.2 7B | Ollama, 4-bit |
| Avatar Gen | 2-3s | Flux 1.1 FP8 | WaveSpeed cache |
| Video Gen | 5-8s | Wan 2.2 FP8 | WaveSpeed cache |
| TTS | 1-2s | CosyVoice3 | Streamed generation |
| Lip Sync | +1s | SadTalker | 256px mode |
| **Total** | **<5s** | Pipeline | Parallel execution |

## Model Specifications

### Flux 1.1 Dev (Image Generation)

```yaml
Model: flux1-dev-fp8.safetensors
Size: ~17GB (FP8)
Resolution: 768x1344 (portrait)
CFG Scale: 3.5
Steps: 6-8
Sampler: euler/simple
Optimizations:
  - WaveSpeed First Block Cache
  - FP8 weight quantization
  - Flash Attention 2
VRAM Usage: ~12GB
```

### Wan 2.2 I2V (Video Generation)

```yaml
Model: wan2.2_i2v_720p_fp8.safetensors
Size: ~30GB (FP8)
Resolution: 1280x720
Frames: 24-48 (1-2 seconds)
Steps: 6
Cache Strength: 0.15
Optimizations:
  - WaveSpeed First Block Cache
  - WaveSpeed Cache Settings node
VRAM Usage: ~18GB
```

### Qwen2-VL (Vision Language)

```yaml
Model: Qwen/Qwen2-VL-7B
Size: ~15GB
Quantization: INT8/INT4
Max Tokens: 100
Temperature: 0.7
VRAM Usage: ~8GB (INT8)
```

### Llama 3.2 (Language Model)

```yaml
Model: llama3.2:7b
Size: ~4GB (4-bit)
Context: 4096 tokens
Temperature: 0.8
Max Tokens: 150
Runtime: Ollama
VRAM Usage: ~6GB
```

### CosyVoice3 (Text-to-Speech)

```yaml
Model: CosyVoice3
Sample Rate: 24000 Hz
Speed: 0.9-1.2 (emotion dependent)
Pitch: 0.95-1.1 (emotion dependent)
Latency: ~1-2s for 10s audio
VRAM Usage: ~2GB
```

### SadTalker (Lip Sync)

```yaml
Model: SadTalker_V0.0.2_256.safetensors
Input: Image + Audio
Output: Video (25 FPS)
Resolution: 256x256 (upscaled)
Mode: full / crop
VRAM Usage: ~4GB
```

## WaveSpeed Integration

### First Block Cache

WaveSpeed's First Block Cache stores intermediate activations from the first transformer block, avoiding redundant computation.

```python
# Workflow integration
WaveSpeed_FirstBlockCache:
  enabled: true
  placement: Before KSampler

# Cache strength for video
WaveSpeed_CacheSettings:
  strength: 0.15  # 0.0-1.0
  mode: balanced  # speed/quality/balanced
```

### Performance Gains

| Model | Without WaveSpeed | With WaveSpeed | Speedup |
|-------|------------------|----------------|---------|
| Flux 1.1 | 60s | 20s | 3x |
| Wan 2.2 | 15min | 8min | 1.9x |
| SDXL | 15s | 7s | 2.1x |

### Stacking with TC Cache

```yaml
# Maximum speed configuration
pipeline:
  - TC_Cache  # 50% speedup
  - WaveSpeed_FirstBlockCache  # Additional 50%
  # Total: ~3x speedup
```

## Memory Management

### VRAM Allocation (RTX 4090 24GB)

```
ComfyUI + Models: ~18GB
System Reserve: ~2GB
Buffer: ~4GB
Total: 24GB
```

### Optimization Strategies

1. **Model Offloading**: CPU offload for unused models
2. **Batch Processing**: Queue multiple requests
3. **FP8 Precision**: Reduces memory by 50%
4. **Attention Slicing**: For high resolutions
5. **WaveSpeed Cache**: Reduces activation memory

## Scalability

### Horizontal Scaling

```
Load Balancer
    │
    ├── ComfyUI Instance 1 (RTX 4090)
    ├── ComfyUI Instance 2 (RTX 4090)
    └── ComfyUI Instance 3 (RTX 4090)
```

### Redis Queue (Optional)

```python
# For multi-pod deployment
REDIS_URL=redis://redis-cluster:6379/0

# Celery workers for background tasks
celery -A backend.core.tasks worker --pool=prefork --concurrency=4
```

## Security Considerations

### API Security

```yaml
# Production settings
security:
  api_key_required: true
  rate_limiting: 10/minute per user
  cors_origins:
    - "https://yourdomain.com"
  max_request_size: 10MB
```

### Model Safety

- Input validation for prompts
- Content filtering (NSFW detection)
- User authentication
- Request logging

## Monitoring

### Metrics to Track

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Generation Latency | <5s | >10s |
| GPU Utilization | 80-95% | <50% or >98% |
| VRAM Usage | <20GB | >22GB |
| Queue Depth | <5 | >20 |
| Error Rate | <1% | >5% |

### Logging

```python
# Structured logging
{
    "timestamp": "2025-01-15T10:30:00Z",
    "level": "INFO",
    "component": "pipeline",
    "event": "generation_complete",
    "user_id": "user_123",
    "request_id": "req_456",
    "stages": {
        "vlm": 0.4,
        "llm": 0.8,
        "avatar": 2.1,
        "video": 5.2,
        "tts": 1.5,
        "lipsync": 0.9
    },
    "total_time": 10.9
}
```

## Deployment Patterns

### Development

```
Local Machine
├── ComfyUI (GPU)
├── Backend (CPU/GPU)
└── Ollama (CPU)
```

### Production (Single Pod)

```
RunPod Pod (RTX 4090)
├── ComfyUI (Docker)
├── Backend API (Docker)
├── Ollama (Docker)
└── Persistent Volume (Models)
```

### Production (Multi-Pod)

```
Kubernetes Cluster
├── ComfyUI Pods (GPU nodes)
├── Backend Pods (CPU nodes)
├── Redis (Queue)
├── PostgreSQL (Memory persistence)
└── Load Balancer
```
