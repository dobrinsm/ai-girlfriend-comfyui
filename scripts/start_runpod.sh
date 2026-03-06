#!/bin/bash
# AI Girlfriend - Complete Startup Script for RunPod
# Run this inside your RunPod pod after setting up

set -e

echo "=========================================="
echo "AI Girlfriend - Starting All Services"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
COMFYUI_DIR="/workspace/ComfyUI"
PROJECT_DIR="/runpod-volume/ai-girlfriend-comfyui"
COSYVOICE_DIR="/runpod-volume/CosyVoice"
LOG_DIR="/runpod-volume/logs"

# Create log directory
mkdir -p "$LOG_DIR"

# Function to check if process is running
is_running() {
    pgrep -f "$1" > /dev/null 2>&1
}

# ========================================
# 1. START COMFYUI
# ========================================
echo ""
echo -e "${GREEN}Step 1: Starting ComfyUI...${NC}"
if ! is_running "comfyui.*main.py"; then
    cd "$COMFYUI_DIR"
    nohup python main.py --listen 0.0.0.0 --port 8188 --preview-method auto > "$LOG_DIR/comfyui.log" 2>&1 &
    echo "  ComfyUI starting on port 8188..."
    sleep 15
else
    echo -e "  ${YELLOW}ComfyUI already running${NC}"
fi

# Wait for ComfyUI to be ready
echo "  Waiting for ComfyUI to be ready..."
for i in {1..30}; do
    if curl -sf http://localhost:8188/system_stats > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ ComfyUI is ready!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "  ${RED}✗ ComfyUI failed to start. Check logs: $LOG_DIR/comfyui.log${NC}"
    fi
    sleep 2
done

# ========================================
# 2. START OLLAMA
# ========================================
echo ""
echo -e "${GREEN}Step 2: Starting Ollama...${NC}"
if ! command -v ollama &> /dev/null; then
    echo "  Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

if ! is_running "ollama serve"; then
    nohup ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
    echo "  Ollama starting on port 11434..."
    sleep 5
    
    # Pull model if not exists
    if ! ollama list | grep -q "llama3.2"; then
        echo "  Pulling llama3.2:7b model (this may take a few minutes)..."
        ollama pull llama3.2:7b
    fi
else
    echo -e "  ${YELLOW}Ollama already running${NC}"
fi

# ========================================
# 3. START COSYVOICE
# ========================================
echo ""
echo -e "${GREEN}Step 3: Starting CosyVoice...${NC}"

# Check if CosyVoice is installed
if [ ! -d "$COSYVOICE_DIR" ]; then
    echo "  Cloning CosyVoice..."
    cd /runpod-volume
    git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git CosyVoice
    cd CosyVoice
    pip install -r requirements.txt
fi

# Start CosyVoice on port 50000 (NOT 8000 - that's used by backend!)
if ! is_running "cosyvoice.*--port 50000"; then
    cd "$COSYVOICE_DIR"
    # Use port 50000 to avoid conflict with backend
    nohup python webui.py --port 50000 > "$LOG_DIR/cosyvoice.log" 2>&1 &
    echo "  CosyVoice starting on port 50000..."
    sleep 10
else
    echo -e "  ${YELLOW}CosyVoice already running${NC}"
fi

# Wait for CosyVoice
echo "  Waiting for CosyVoice..."
for i in {1..20}; do
    if curl -sf http://localhost:50000 > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ CosyVoice is ready!${NC}"
        break
    fi
    if [ $i -eq 20 ]; then
        echo -e "  ${YELLOW}! CosyVoice may still be loading (check $LOG_DIR/cosyvoice.log)${NC}"
    fi
    sleep 3
done

# ========================================
# 4. START BACKEND
# ========================================
echo ""
echo -e "${GREEN}Step 4: Starting Backend API...${NC}"

cd "$PROJECT_DIR/backend"

# Make sure .env has correct CosyVoice port
if grep -q "COSYVOICE_SERVER=http://localhost:8000" .env 2>/dev/null; then
    echo "  Updating CosyVoice port in .env to 50000..."
    sed -i 's|COSYVOICE_SERVER=http://localhost:8000|COSYVOICE_SERVER=http://localhost:50000|g' .env
fi

if ! is_running "uvicorn.*main:app"; then
    nohup python main.py > "$LOG_DIR/backend.log" 2>&1 &
    echo "  Backend starting on port 8000..."
    sleep 5
else
    echo -e "  ${YELLOW}Backend already running${NC}"
fi

# Wait for backend
echo "  Waiting for Backend..."
for i in {1..15}; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ Backend is ready!${NC}"
        break
    fi
    if [ $i -eq 15 ]; then
        echo -e "  ${RED}✗ Backend failed to start. Check logs: $LOG_DIR/backend.log${NC}"
    fi
    sleep 2
done

# ========================================
# 5. VERIFY ALL SERVICES
# ========================================
echo ""
echo "=========================================="
echo -e "${GREEN}Services Status:${NC}"
echo "=========================================="

echo -n "ComfyUI (port 8188):  "
curl -sf http://localhost:8188/system_stats > /dev/null 2>&1 && echo -e "${GREEN}✓ Running${NC}" || echo -e "${RED}✗ Not running${NC}"

echo -n "Ollama (port 11434):  "
curl -sf http://localhost:11434/api/tags > /dev/null 2>&1 && echo -e "${GREEN}✓ Running${NC}" || echo -e "${RED}✗ Not running${NC}"

echo -n "CosyVoice (port 50000): "
curl -sf http://localhost:50000 > /dev/null 2>&1 && echo -e "${GREEN}✓ Running${NC}" || echo -e "${YELLOW}! Starting${NC}"

echo -n "Backend (port 8000):   "
curl -sf http://localhost:8000/health > /dev/null 2>&1 && echo -e "${GREEN}✓ Running${NC}" || echo -e "${RED}✗ Not running${NC}"

echo ""
echo "=========================================="
echo -e "${GREEN}Access URLs (via RunPod Proxy):${NC}"
echo "=========================================="
echo ""
echo "  Find your Pod ID in RunPod Console → Connect"
echo ""
echo "  Replace <pod-id> with your actual Pod ID:"
echo ""
echo "  • ComfyUI:   https://<pod-id>-8188.proxy.runpod.net"
echo "  • Backend:   https://<pod-id>-8000.proxy.runpod.net"
echo "  • API Docs:  https://<pod-id>-8000.proxy.runpod.net/docs"
echo ""
echo "=========================================="
echo ""
echo "To view logs:"
echo "  ComfyUI:   tail -f $LOG_DIR/comfyui.log"
echo "  Backend:   tail -f $LOG_DIR/backend.log"
echo "  Ollama:    tail -f $LOG_DIR/ollama.log"
echo "  CosyVoice: tail -f $LOG_DIR/cosyvoice.log"
echo ""
echo "=========================================="
