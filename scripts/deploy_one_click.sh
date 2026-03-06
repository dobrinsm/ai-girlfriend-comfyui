#!/bin/bash
# One-command RunPod deployment - clones repo, builds and starts all services

set -e

echo "=========================================="
echo "AI Girlfriend - One-Click Deploy"
echo "=========================================="

# Check we're on RunPod
if [ ! -d "/runpod-volume" ]; then
    echo "Error: This script must be run inside a RunPod"
    exit 1
fi

PROJECT_DIR="/runpod-volume/ai-girlfriend-comfyui"

# Step 1: Clone repo if not exists
echo "Step 1: Cloning repository..."
if [ ! -d "$PROJECT_DIR" ]; then
    cd /runpod-volume
    git clone https://github.com/dobrinsm/ai-girlfriend-comfyui.git
fi

cd "$PROJECT_DIR"

# Step 2: Create necessary directories
echo "Step 2: Creating directories..."
mkdir -p /runpod-volume/{data,outputs,logs}
mkdir -p ComfyUI/{models,output,custom_nodes}

# Step 3: Check Docker
echo "Step 3: Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "Error: Docker not installed"
    exit 1
fi

# Step 4: Create CosyVoice docker image (if not exists)
echo "Step 4: Building CosyVoice image..."
if ! docker image ls cosyvoice -q &> /dev/null; then
    cd ../CosyVoice
    docker build -t cosyvoice:latest -f docker/Dockerfile .
    cd "$PROJECT_DIR"
fi

# Step 5: Build other images
echo "Step 5: Building service images..."
docker-compose build

# Step 6: Start all services
echo "Step 6: Starting all services..."
docker-compose up -d

# Step 7: Wait for services
echo "Step 7: Waiting for services to be ready..."
sleep 30

# Check health
echo ""
echo "=========================================="
echo "Services Status:"
echo "=========================================="

for service in comfyui backend ollama cosyvoice; do
    status=$(docker-compose ps $service | grep -c "Up" 2>/dev/null || echo "0")
    if [ "$status" -gt "0" ]; then
        echo "  ✓ $service is running"
    else
        echo "  ✗ $service may have issues"
    fi
done

echo ""
echo "=========================================="
echo "To access services:"
echo "=========================================="
echo "Find your Pod ID in RunPod Console → Connect"
echo ""
echo "  • Backend:   https://<pod-id>-8000.proxy.runpod.net"
echo "  • ComfyUI:  https://<pod-id>-8188.proxy.runpod.net"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""
