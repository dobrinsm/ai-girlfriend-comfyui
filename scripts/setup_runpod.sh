#!/bin/bash
# AI Girlfriend - One-Click Setup for RunPod (No Network Volume Required)
# All data is stored in /workspace (container disk)

set -e

echo "=========================================="
echo "AI Girlfriend - RunPod Setup"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration - Using /workspace (container disk) instead of network volume
WORKSPACE="/workspace"
PROJECT_DIR="$WORKSPACE/ai-girlfriend-comfyui"
MODELS_DIR="$WORKSPACE/models"
COMFYUI_DIR="$WORKSPACE/ComfyUI"
LOG_DIR="$WORKSPACE/logs"

# ========================================
# 1. Check Environment
# ========================================
echo ""
echo -e "${BLUE}Step 1: Checking environment...${NC}"

# Check GPU
if command -v nvidia-smi &> /dev/null; then
    GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
    VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader | head -1)
    echo -e "  ${GREEN}✓${NC} GPU: $GPU ($VRAM)"
else
    echo -e "  ${RED}✗${NC} No GPU detected"
    exit 1
fi

# Check disk space
DISK=$(df -h "$WORKSPACE" | tail -1 | awk '{print $4}')
echo -e "  ${GREEN}✓${NC} Available disk: $DISK"

# ========================================
# 2. Install System Dependencies
# ========================================
echo ""
echo -e "${BLUE}Step 2: Installing system dependencies...${NC}"

apt-get update -qq
apt-get install -y -qq git wget curl vim libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev

echo -e "  ${GREEN}✓${NC} System dependencies installed"

# ========================================
# 3. Create Directories
# ========================================
echo ""
echo -e "${BLUE}Step 3: Creating directories...${NC}"

mkdir -p "$MODELS_DIR"/{checkpoints,clip,vae,loras,ipadapter,sadtalker,embeddings,controlnet}
mkdir -p "$WORKSPACE/outputs"
mkdir -p "$WORKSPACE/data"
mkdir -p "$LOG_DIR"

echo -e "  ${GREEN}✓${NC} Directories created at $WORKSPACE"

# ========================================
# 4. Clone Project
# ========================================
echo ""
echo -e "${BLUE}Step 4: Cloning project...${NC}"

cd "$WORKSPACE"

if [ ! -d "$PROJECT_DIR" ]; then
    git clone https://github.com/dobrinsm/ai-girlfriend-comfyui.git "$PROJECT_DIR"
    echo -e "  ${GREEN}✓${NC} Project cloned"
else
    echo -e "  ${YELLOW}!${NC} Project already exists, pulling updates..."
    cd "$PROJECT_DIR"
    git pull
fi

# ========================================
# 5. Setup ComfyUI
# ========================================
echo ""
echo -e "${BLUE}Step 5: Setting up ComfyUI...${NC}"

if [ ! -d "$COMFYUI_DIR" ]; then
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git "$COMFYUI_DIR"
    echo -e "  ${GREEN}✓${NC} ComfyUI cloned"
else
    echo -e "  ${YELLOW}!${NC} ComfyUI already exists"
fi

cd "$COMFYUI_DIR"
pip install -q -r requirements.txt

# Install custom nodes
echo "  Installing custom nodes..."
cd "$COMFYUI_DIR/custom_nodes"

install_node() {
    local repo=$1
    local name=$(basename "$repo" .git)
    
    if [ ! -d "$name" ]; then
        echo "    - $name"
        git clone --depth 1 "$repo" "$name"
        if [ -f "$name/requirements.txt" ]; then
            pip install -q -r "$name/requirements.txt" || true
        fi
    fi
}

install_node "https://github.com/chengzeyi/Comfy-WaveSpeed.git"
install_node "https://github.com/ltdrdata/ComfyUI-Manager.git"
install_node "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git"
install_node "https://github.com/cubiq/ComfyUI_IPAdapter_plus.git"
install_node "https://github.com/OpenTalker/SadTalker.git"

# Create symlinks for models
cd "$COMFYUI_DIR/models"
for dir in checkpoints clip vae loras ipadapter sadtalker embeddings controlnet; do
    if [ -d "$MODELS_DIR/$dir" ] && [ ! -L "$dir" ]; then
        rm -rf "${dir}_backup" 2>/dev/null || true
        mv "$dir" "${dir}_backup" 2>/dev/null || true
        ln -sf "$MODELS_DIR/$dir" "$dir"
    elif [ ! -L "$dir" ]; then
        ln -sf "$MODELS_DIR/$dir" "$dir"
    fi
done

echo -e "  ${GREEN}✓${NC} ComfyUI setup complete"

# ========================================
# 6. Install Backend Dependencies
# ========================================
echo ""
echo -e "${BLUE}Step 6: Installing backend dependencies...${NC}"

cd "$PROJECT_DIR/backend"
pip install -q -r requirements.txt

# Create .env file
cat > "$PROJECT_DIR/backend/.env" << EOF
DEBUG=false
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
COMFYUI_URL=http://localhost:8188
COMFYUI_WS_URL=ws://localhost:8188/ws
WORKFLOW_DIR=$PROJECT_DIR/workflows
OUTPUT_DIR=$WORKSPACE/outputs
OLLAMA_HOST=http://localhost:11434
COSYVOICE_SERVER=http://localhost:50000
VLM_MODEL=qwen2-vl-7b
LLM_MODEL=llama3.2:7b
TTS_MODEL=cosyvoice3
TTS_VOICE_ID=friendly_female
MEMORY_DB_PATH=$WORKSPACE/data/memory.db
MAX_MEMORY_ITEMS=50
DEFAULT_CFG=3.5
DEFAULT_STEPS=6
WAVESPEED_CACHE=true
CACHE_STRENGTH=0.15
MAX_CONCURRENT_GENERATIONS=2
REQUEST_TIMEOUT=300
EOF

echo -e "  ${GREEN}✓${NC} Backend setup complete"

# ========================================
# 7. Download Models
# ========================================
echo ""
echo -e "${BLUE}Step 7: Downloading models...${NC}"
echo -e "  ${YELLOW}This may take 30-60 minutes depending on your connection${NC}"

cd "$PROJECT_DIR"
python scripts/download_models.py --all

echo -e "  ${GREEN}✓${NC} Models downloaded"

# ========================================
# 8. Create Startup Script
# ========================================
echo ""
echo -e "${BLUE}Step 8: Creating startup script...${NC}"

cat > "$WORKSPACE/start_ai_girlfriend.sh" << 'SCRIPT'
#!/bin/bash
# AI Girlfriend - Start All Services

WORKSPACE="/workspace"
PROJECT_DIR="$WORKSPACE/ai-girlfriend-comfyui"
LOG_DIR="$WORKSPACE/logs"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

echo "Starting AI Girlfriend services..."

# ComfyUI
if ! is_running "ComfyUI/main.py"; then
    echo "  Starting ComfyUI..."
    cd "$WORKSPACE/ComfyUI"
    nohup python main.py --listen 0.0.0.0 --port 8188 --preview-method auto > "$LOG_DIR/comfyui.log" 2>&1 &
    sleep 15
else
    echo -e "  ${YELLOW}ComfyUI already running${NC}"
fi

# Wait for ComfyUI
echo "  Waiting for ComfyUI..."
for i in {1..30}; do
    if curl -sf http://localhost:8188/system_stats > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ ComfyUI ready${NC}"
        break
    fi
    sleep 2
done

# Ollama
if ! command -v ollama &> /dev/null; then
    echo "  Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

if ! is_running "ollama serve"; then
    echo "  Starting Ollama..."
    nohup ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
    sleep 5
    
    if ! ollama list | grep -q "llama3.2"; then
        echo "  Pulling llama3.2:7b (this may take a few minutes)..."
        ollama pull llama3.2:7b
    fi
else
    echo -e "  ${YELLOW}Ollama already running${NC}"
fi

# Frontend
if ! is_running "frontend/serve.py"; then
    echo "  Starting Frontend..."
    cd "$PROJECT_DIR/frontend"
    nohup python serve.py > "$LOG_DIR/frontend.log" 2>&1 &
    sleep 2
else
    echo -e "  ${YELLOW}Frontend already running${NC}"
fi

# Backend
if ! is_running "uvicorn.*main:app"; then
    echo "  Starting Backend API..."
    cd "$PROJECT_DIR/backend"
    nohup python main.py > "$LOG_DIR/backend.log" 2>&1 &
    sleep 5
else
    echo -e "  ${YELLOW}Backend already running${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Services Status:${NC}"
echo "=========================================="
echo -n "ComfyUI (8188):  "
curl -sf http://localhost:8188/system_stats > /dev/null 2>&1 && echo -e "${GREEN}✓ Running${NC}" || echo -e "${RED}✗ Not running${NC}"
echo -n "Ollama (11434):  "
curl -sf http://localhost:11434/api/tags > /dev/null 2>&1 && echo -e "${GREEN}✓ Running${NC}" || echo -e "${RED}✗ Not running${NC}"
echo -n "Frontend (3000):  "
curl -sf http://localhost:3000 > /dev/null 2>&1 && echo -e "${GREEN}✓ Running${NC}" || echo -e "${YELLOW}! Starting${NC}"
echo -n "Backend (8000):   "
curl -sf http://localhost:8000/health > /dev/null 2>&1 && echo -e "${GREEN}✓ Running${NC}" || echo -e "${RED}✗ Not running${NC}"
echo ""
echo "Access via RunPod Proxy:"
echo "  - Frontend:   https://<pod-id>-3000.proxy.runpod.net"
echo "  - ComfyUI:   https://<pod-id>-8188.proxy.runpod.net"
echo "  - Backend:   https://<pod-id>-8000.proxy.runpod.net"
echo ""
echo "Find your Pod ID in RunPod Console → Connect"
echo "=========================================="
SCRIPT

chmod +x "$WORKSPACE/start_ai_girlfriend.sh"

echo -e "  ${GREEN}✓${NC} Startup script created"

# ========================================
# 9. Start Services
# ========================================
echo ""
echo -e "${BLUE}Step 9: Starting services...${NC}"

bash "$WORKSPACE/start_ai_girlfriend.sh"

# ========================================
# Summary
# ========================================
echo ""
echo "=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Project location: $PROJECT_DIR"
echo "Models location: $MODELS_DIR"
echo "Logs location: $LOG_DIR"
echo ""
echo "To restart services:"
echo "  bash $WORKSPACE/start_ai_girlfriend.sh"
echo ""
echo "To view logs:"
echo "  tail -f $LOG_DIR/comfyui.log"
echo "  tail -f $LOG_DIR/backend.log"
echo ""
echo "Access via RunPod proxy:"
echo "  - ComfyUI:   https://<pod-id>-8188.proxy.runpod.net"
echo "  - Backend:   https://<pod-id>-8000.proxy.runpod.net"
echo ""
echo "Find your Pod ID in RunPod Console → Connect"
echo "=========================================="
