#!/bin/bash
set -e

echo "========================================"
echo "AI Girlfriend - RunPod Deployment"
echo "========================================"

# Configuration
TEMPLATE_NAME="ai-girlfriend-comfyui"
GPU_TYPE="NVIDIA RTX 4090"
GPU_COUNT=1
VCPU_COUNT=8
MEMORY_GB=32
VOLUME_SIZE_GB=100

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check for RunPod CLI
if ! command -v runpodctl &> /dev/null; then
    echo -e "${RED}Error: runpodctl not found${NC}"
    echo "Install from: https://github.com/runpod/runpodctl"
    exit 1
fi

# Check login status
echo "Checking RunPod authentication..."
if ! runpodctl config 2>/dev/null | grep -q "apiKey"; then
    echo -e "${YELLOW}Please login to RunPod first:${NC}"
    runpodctl config --apiKey YOUR_API_KEY
    exit 1
fi

echo -e "${GREEN}Authenticated with RunPod${NC}"

# Build and push Docker image
echo ""
echo "Building Docker image..."
cd ../docker
docker build -t $TEMPLATE_NAME:latest -f Dockerfile.comfyui .

# Tag for registry (adjust as needed)
# docker tag $TEMPLATE_NAME:latest your-registry/$TEMPLATE_NAME:latest
# docker push your-registry/$TEMPLATE_NAME:latest

echo -e "${GREEN}Docker image built${NC}"

# Create pod template
echo ""
echo "Creating RunPod template..."

# Option 1: Use runpodctl
# runpodctl create pod \
#     --name "$TEMPLATE_NAME" \
#     --imageName "$TEMPLATE_NAME:latest" \
#     --gpuType "$GPU_TYPE" \
#     --gpuCount $GPU_COUNT \
#     --vcpu $VCPU_COUNT \
#     --mem $MEMORY_GB \
#     --volumeSize $VOLUME_SIZE_GB \
#     --ports "8188:8188,8000:8000" \
#     --env "DOWNLOAD_MODELS=false" \
#     --env "WAVESPEED_CACHE=true"

# Option 2: Use template JSON
echo "Template configuration:"
cat pod-template.json | jq .

echo ""
echo -e "${YELLOW}To deploy manually:${NC}"
echo "1. Go to https://www.runpod.io/console/pods"
echo "2. Click 'Deploy'"
echo "3. Select 'Custom Template'"
echo "4. Upload the pod-template.json file"
echo "5. Configure your network volume for persistent storage"
echo ""
echo -e "${GREEN}Deployment guide ready!${NC}"

# Create network volume if needed
echo ""
read -p "Create persistent network volume? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Creating network volume (${VOLUME_SIZE_GB}GB)..."
    # runpodctl create volume --name "ai-girlfriend-models" --size $VOLUME_SIZE_GB
    echo -e "${YELLOW}Note: Uncomment the runpodctl command to auto-create volume${NC}"
fi

echo ""
echo "========================================"
echo "Deployment preparation complete!"
echo "========================================"
