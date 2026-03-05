#!/bin/bash
# One-click setup script for RunPod deployment
# Run this inside your RunPod pod

set -e

echo "=========================================="
echo "AI Girlfriend - RunPod Setup"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
PROJECT_DIR="/runpod-volume/ai-girlfriend-comfyui"
MODELS_DIR="/runpod-volume/models"
COMFYUI_DIR="/workspace/ComfyUI"

# Check if running on RunPod
if [ ! -d "/runpod-volume" ]; then
    echo -e "${RED}Error: /runpod-volume not found${NC}"
    echo "Are you running this on RunPod?"
    exit 1
fi

echo -e "${GREEN}✓ Running on RunPod${NC}"

# Check GPU
echo ""
echo "Checking GPU..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
else
    echo -e "${RED}Warning: nvidia-smi not found${NC}"
fi

# Step 1: Install system dependencies
echo ""
echo "Step 1: Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq git wget curl vim libgl1-mesa-glx libglib2.0-0

# Step 2: Setup directories
echo ""
echo "Step 2: Setting up directories..."
mkdir -p "$MODELS_DIR"/{checkpoints,clip,vae,loras,ipadapter,sadtalker,embeddings,controlnet}
mkdir -p /runpod-volume/outputs
mkdir -p /runpod-volume/data

# Step 3: Install Python dependencies
echo ""
echo "Step 3: Installing Python dependencies..."
pip install -q --upgrade pip

# Install PyTorch with CUDA
pip install -q torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121

# Install Triton for WaveSpeed
pip install -q triton

# Step 4: Clone ComfyUI
echo ""
echo "Step 4: Setting up ComfyUI..."
if [ ! -d "$COMFYUI_DIR" ]; then
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git "$COMFYUI_DIR"
    cd "$COMFYUI_DIR"
    pip install -q -r requirements.txt
else
    echo "ComfyUI already exists, updating..."
    cd "$COMFYUI_DIR"
    git pull
fi

# Step 5: Install custom nodes
echo ""
echo "Step 5: Installing custom nodes..."
cd "$COMFYUI_DIR/custom_nodes"

install_node() {
    local repo=$1
    local name=$(basename "$repo" .git)

    if [ ! -d "$name" ]; then
        echo "  Installing $name..."
        git clone --depth 1 "$repo" "$name"
        if [ -f "$name/requirements.txt" ]; then
            pip install -q -r "$name/requirements.txt" || true
        fi
    else
        echo "  Updating $name..."
        cd "$name" && git pull && cd ..
    fi
}

install_node "https://github.com/chengzeyi/Comfy-WaveSpeed.git"
install_node "https://github.com/ltdrdata/ComfyUI-Manager.git"
install_node "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git"
install_node "https://github.com/cubiq/ComfyUI_IPAdapter_plus.git"
install_node "https://github.com/OpenTalker/SadTalker.git"

# Step 6: Create symlinks for models
echo ""
echo "Step 6: Creating model symlinks..."
cd "$COMFYUI_DIR/models"

for dir in checkpoints clip vae loras ipadapter sadtalker; do
    if [ -d "$MODELS_DIR/$dir" ]; then
        # Backup existing directory
        if [ -d "$dir" ] && [ ! -L "$dir" ]; then
            mv "$dir" "${dir}_backup_$(date +%s)"
        fi
        # Create symlink
        if [ ! -L "$dir" ]; then
            ln -sf "$MODELS_DIR/$dir" "$dir"
            echo "  Linked $dir"
        fi
    fi
done

# Step 7: Setup project files
echo ""
echo "Step 7: Setting up project files..."
if [ ! -d "$PROJECT_DIR" ]; then
    mkdir -p "$PROJECT_DIR"
    echo "  Created project directory"
fi

# Create a minimal backend setup
cd "$PROJECT_DIR"
mkdir -p backend workflows configs scripts

# Create requirements.txt for backend
cat > backend/requirements.txt << 'EOF'
fastapi==0.115.0
uvicorn[standard]==0.32.0
websockets==13.1
pydantic==2.9.2
pydantic-settings==2.6.1
httpx==0.27.2
aiofiles==24.1.0
python-multipart==0.0.17
pillow==11.0.0
numpy==1.26.4
sqlalchemy==2.0.36
aiosqlite==0.20.0
ollama==0.4.2
EOF

# Create .env for backend
cat > backend/.env << EOF
DEBUG=false
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
COMFYUI_URL=http://localhost:8188
COMFYUI_WS_URL=ws://localhost:8188/ws
WORKFLOW_DIR=$PROJECT_DIR/workflows
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

# Install backend dependencies
pip install -q -r backend/requirements.txt

# Step 8: Create startup script
echo ""
echo "Step 8: Creating startup script..."
cat > /runpod-volume/start_all.sh << 'EOF'
#!/bin/bash

echo "=========================================="
echo "Starting AI Girlfriend Services"
echo "=========================================="

# Function to check if process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# Start ComfyUI
echo "Starting ComfyUI..."
if ! is_running "ComfyUI/main.py"; then
    cd /workspace/ComfyUI
    python main.py --listen 0.0.0.0 --port 8188 --preview-method auto > /runpod-volume/logs/comfyui.log 2>&1 &
    echo "  ComfyUI starting on port 8188..."
    sleep 10
else
    echo "  ComfyUI already running"
fi

# Start Backend
echo "Starting Backend API..."
if ! is_running "ai-girlfriend-comfyui/backend/main.py"; then
    cd /runpod-volume/ai-girlfriend-comfyui/backend
    python main.py > /runpod-volume/logs/backend.log 2>&1 &
    echo "  Backend starting on port 8000..."
    sleep 5
else
    echo "  Backend already running"
fi

# Check Ollama
echo "Checking Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "  Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

if ! is_running "ollama serve"; then
    echo "  Starting Ollama..."
    ollama serve > /runpod-volume/logs/ollama.log 2>&1 &
    sleep 5

    # Pull model if not exists
    if ! ollama list | grep -q "llama3.2"; then
        echo "  Pulling llama3.2:7b model..."
        ollama pull llama3.2:7b
    fi
else
    echo "  Ollama already running"
fi

echo ""
echo "=========================================="
echo "Services Status:"
echo "=========================================="
echo "ComfyUI:  http://$(hostname -I | awk '{print $1}'):8188"
echo "Backend:  http://$(hostname -I | awk '{print $1}'):8000"
echo "API Docs: http://$(hostname -I | awk '{print $1}'):8000/docs"
echo "=========================================="
echo ""
echo "To view logs:"
echo "  ComfyUI: tail -f /runpod-volume/logs/comfyui.log"
echo "  Backend: tail -f /runpod-volume/logs/backend.log"
echo "  Ollama:  tail -f /runpod-volume/logs/ollama.log"
EOF

chmod +x /runpod-volume/start_all.sh
mkdir -p /runpod-volume/logs

# Step 9: Create model download script
echo ""
echo "Step 9: Creating model download script..."
cat > /runpod-volume/download_models.sh << 'EOF'
#!/bin/bash

MODELS_DIR="/runpod-volume/models"

echo "Downloading AI Girlfriend Models..."
echo "This may take 30-60 minutes depending on your connection."
echo ""

# Function to download with progress
download_model() {
    local url=$1
    local dest=$2
    local name=$(basename "$dest")

    if [ -f "$dest" ]; then
        echo "  ✓ $name already exists"
        return
    fi

    echo "  ↓ Downloading $name..."
    wget -q --show-progress -O "$dest" "$url" || echo "  ✗ Failed to download $name"
}

# Create directories
mkdir -p "$MODELS_DIR"/{checkpoints,clip,vae,ipadapter}

echo "Downloading Flux models..."
download_model \
    "https://huggingface.co/Kijai/flux-fp8/resolve/main/flux1-dev-fp8.safetensors" \
    "$MODELS_DIR/checkpoints/flux1-dev-fp8.safetensors"

echo "Downloading text encoders..."
download_model \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" \
    "$MODELS_DIR/clip/clip_l.safetensors"

download_model \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors" \
    "$MODELS_DIR/clip/t5xxl_fp8_e4m3fn.safetensors"

echo "Downloading VAE..."
download_model \
    "https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors" \
    "$MODELS_DIR/vae/ae.safetensors"

echo ""
echo "Essential models downloaded!"
echo "Optional: Download Wan 2.2 models for video generation:"
echo "  - https://huggingface.co/Wan-AI/Wan2.1-I2V-14B-720P"
echo ""
echo "Models location: $MODELS_DIR"
ls -lh "$MODELS_DIR/checkpoints/"
EOF

chmod +x /runpod-volume/download_models.sh

# Summary
echo ""
echo "=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Download models:"
echo "   /runpod-volume/download_models.sh"
echo ""
echo "2. Start all services:"
echo "   /runpod-volume/start_all.sh"
echo ""
echo "3. Access your services:"
echo "   - ComfyUI: http://<pod-ip>:8188"
echo "   - Backend: http://<pod-ip>:8000"
echo ""
echo "4. Find your pod IP in the RunPod console"
echo ""
echo "Project location: $PROJECT_DIR"
echo "Models location: $MODELS_DIR"
echo "Logs location: /runpod-volume/logs"
echo ""
echo "=========================================="
