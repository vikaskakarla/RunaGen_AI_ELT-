#!/bin/bash

# Deploy RunaGen to existing Cloud Run URL with Ollama
# This updates the existing runagen-api service

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Deploy to Existing Cloud Run URL${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Configuration
GCP_PROJECT_ID="runagen-ai"
SERVICE_NAME="runagen-api"
REGION="us-central1"
IMAGE_NAME="gcr.io/${GCP_PROJECT_ID}/${SERVICE_NAME}"
OLLAMA_INSTANCE="runagen-ollama"
OLLAMA_ZONE="us-central1-a"
OLLAMA_MACHINE="n1-standard-2"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not found${NC}"
    exit 1
fi
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Prerequisites met${NC}\n"

# Set project
echo -e "${YELLOW}Setting GCP project...${NC}"
gcloud config set project $GCP_PROJECT_ID
echo -e "${GREEN}✓ Project set${NC}\n"

# Enable APIs
echo -e "${YELLOW}Enabling GCP APIs...${NC}"
gcloud services enable compute.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
echo -e "${GREEN}✓ APIs enabled${NC}\n"

# Step 1: Create Compute Engine instance for Ollama
echo -e "${YELLOW}Step 1: Setting up Ollama on Compute Engine...${NC}"
if gcloud compute instances describe $OLLAMA_INSTANCE --zone=$OLLAMA_ZONE &>/dev/null; then
    echo -e "${YELLOW}⚠ Ollama instance already exists${NC}"
    OLLAMA_EXTERNAL_IP=$(gcloud compute instances describe $OLLAMA_INSTANCE \
        --zone=$OLLAMA_ZONE \
        --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
else
    echo -e "${YELLOW}Creating Compute Engine instance...${NC}"
    gcloud compute instances create $OLLAMA_INSTANCE \
        --zone=$OLLAMA_ZONE \
        --machine-type=$OLLAMA_MACHINE \
        --image-family=ubuntu-2204-lts \
        --image-project=ubuntu-os-cloud \
        --boot-disk-size=50GB \
        --scopes=default,cloud-platform \
        --tags=ollama,http-server,https-server
    
    sleep 10
    
    OLLAMA_EXTERNAL_IP=$(gcloud compute instances describe $OLLAMA_INSTANCE \
        --zone=$OLLAMA_ZONE \
        --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    
    echo -e "${GREEN}✓ Instance created${NC}"
fi

echo -e "${GREEN}✓ Ollama IP: $OLLAMA_EXTERNAL_IP${NC}\n"

# Step 2: Create firewall rule
echo -e "${YELLOW}Step 2: Configuring firewall...${NC}"
if gcloud compute firewall-rules describe allow-ollama-from-cloud-run &>/dev/null; then
    echo -e "${YELLOW}⚠ Firewall rule already exists${NC}"
else
    gcloud compute firewall-rules create allow-ollama-from-cloud-run \
        --allow=tcp:11434 \
        --source-ranges=0.0.0.0/0 \
        --target-tags=ollama
    echo -e "${GREEN}✓ Firewall rule created${NC}"
fi
echo ""

# Step 3: Install Ollama on instance
echo -e "${YELLOW}Step 3: Installing Ollama on Compute Engine...${NC}"
echo -e "${YELLOW}This will take 5-10 minutes (downloading llama3 model)...${NC}\n"

gcloud compute ssh $OLLAMA_INSTANCE --zone=$OLLAMA_ZONE << 'OLLAMA_SETUP'
    set -e
    
    # Update system
    echo "Updating system..."
    sudo apt-get update -qq
    
    # Install Docker if not present
    if ! command -v docker &> /dev/null; then
        echo "Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
        newgrp docker
    fi
    
    # Stop existing Ollama if running
    docker stop ollama 2>/dev/null || true
    docker rm ollama 2>/dev/null || true
    
    # Run Ollama
    echo "Starting Ollama service..."
    docker run -d \
        --name ollama \
        -p 11434:11434 \
        -v ollama_data:/root/.ollama \
        --restart unless-stopped \
        ollama/ollama:latest
    
    # Wait for Ollama to start
    sleep 15
    
    # Pull llama3 model
    echo "Pulling llama3 model (this takes 5-10 minutes)..."
    docker exec ollama ollama pull llama3
    
    # Verify
    echo "Verifying Ollama..."
    curl -s http://localhost:11434/api/tags | grep -q llama3 && echo "✓ Ollama ready with llama3" || echo "⚠ Ollama setup in progress"
OLLAMA_SETUP

echo -e "${GREEN}✓ Ollama installed and ready${NC}\n"

# Step 4: Build Docker image
echo -e "${YELLOW}Step 4: Building Docker image...${NC}"
docker build -t $IMAGE_NAME:latest -f Dockerfile.cloud .
echo -e "${GREEN}✓ Docker image built${NC}\n"

# Step 5: Push to Container Registry
echo -e "${YELLOW}Step 5: Pushing image to Container Registry...${NC}"
docker push $IMAGE_NAME:latest
echo -e "${GREEN}✓ Image pushed${NC}\n"

# Step 6: Deploy to Cloud Run
echo -e "${YELLOW}Step 6: Deploying to Cloud Run...${NC}"
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME:latest \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 3600 \
    --set-env-vars "ENVIRONMENT=cloud,OLLAMA_URL=http://$OLLAMA_EXTERNAL_IP:11434,OLLAMA_MODEL=llama3,GCP_PROJECT_ID=$GCP_PROJECT_ID,PYTHONUNBUFFERED=1,PYTHONPATH=/app/src" \
    --max-instances 100 \
    --min-instances 0

echo -e "${GREEN}✓ Deployed to Cloud Run${NC}\n"

# Get service URL
API_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format='value(status.url)')

# Display summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Deployment Complete ✅${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Service: ${GREEN}$SERVICE_NAME${NC}"
echo -e "Region: ${GREEN}$REGION${NC}"
echo -e "URL: ${GREEN}$API_URL${NC}"
echo -e "Ollama Instance: ${GREEN}$OLLAMA_INSTANCE${NC}"
echo -e "Ollama IP: ${GREEN}$OLLAMA_EXTERNAL_IP${NC}"
echo -e "\n${BLUE}Test Commands:${NC}"
echo -e "  Health: ${GREEN}curl $API_URL/health${NC}"
echo -e "  Analyze: ${GREEN}curl -X POST $API_URL/api/analyze-resume -H 'Content-Type: application/json' -d '{\"resume_text\": \"Python, AWS, Docker\"}'${NC}"
echo -e "\n${BLUE}Monitor:${NC}"
echo -e "  Logs: ${GREEN}gcloud run logs read $SERVICE_NAME --region $REGION --follow${NC}"
echo -e "  Ollama: ${GREEN}gcloud compute ssh $OLLAMA_INSTANCE --zone=$OLLAMA_ZONE${NC}"
echo -e "\n${BLUE}========================================${NC}\n"

echo -e "${GREEN}✅ Your webapp is live at: $API_URL${NC}\n"
