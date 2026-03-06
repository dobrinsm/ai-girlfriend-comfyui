#!/bin/bash
# RunPod CLI Deployment Script
# This creates a pod with all services using docker-compose

set -e

echo "=========================================="
echo "AI Girlfriend - RunPod CLI Deployment"
echo "=========================================="

# Check if runpodctl is installed
if ! command -v runpodctl &> /dev/null; then
    echo "Installing runpodctl..."
    # Linux
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        wget -qO /usr/local/bin/runpodctl https://github.com/runpod/runpodctl/releases/latest/download/runpodctl-linux-amd64
        chmod +x /usr/local/bin/runpodctl
    # macOS
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        brew install runpod/runpodctl/runpodctl
    fi
fi

# Login (you need to provide your API key)
echo "Checking runpodctl configuration..."
runpodctl config --apiKey YOUR_API_KEY

# Create network volume (if not exists)
echo "Creating network volume..."
runpodctl create volume \
    --name ai-girlfriend-models \
    --size 100 \
    --dataCenterId US-OR-1

# Deploy pod with docker-compose support
# Note: RunPod doesn't support docker-compose directly in pod
# So we use a custom template that includes all services

echo "Deploying pod..."
runpodctl create pod \
    --name ai-girlfriend \
    --gpuType "NVIDIA RTX 4090" \
    --imageName "runpod/pytorch:2.1.0-cu118-ubuntu22.04" \
    --volumeSize 100 \
    --volumeName ai-girlfriend-models \
    --containerDiskSize 100 \
    --ports "8188/http,8000/http,11434/http,50000/http" \
    --env "PYTHONUNBUFFERED=1" \
    --env "NVIDIA_VISIBLE_DEVICES=all"

echo ""
echo "=========================================="
echo "Pod deployed! Getting connection info..."
echo "=========================================="

# Get pod info
POD_INFO=$(runpodctl get pod ai-girlfriend -o json)
POD_ID=$(echo $POD_INFO | jq -r '.id')

echo ""
echo "Pod ID: $POD_ID"
echo ""
echo "Wait for pod to be Running, then access services at:"
echo "  • ComfyUI:   https://${POD_ID}-8188.proxy.runpod.net"
echo "  • Backend:   https://${POD_ID}-8000.proxy.runpod.net"
echo "  • Ollama:    https://${POD_ID}-11434.proxy.runpod.net"
echo "  • CosyVoice: https://${POD_ID}-50000.proxy.runpod.net"
echo ""
echo "Once pod is running, SSH in and run:"
echo "  cd /runpod-volume/ai-girlfriend-comfyui"
echo "  docker-compose up -d"
echo ""
