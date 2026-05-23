#!/bin/bash

# Deploy RunaGen with Ollama to Google Cloud
# This script deploys Ollama on Compute Engine and API on Cloud Run

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}RunaGen + Ollama - Cloud Deployment${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Configuration
GCP_PROJECT_ID="runagen-ai"
OLLAMA_INSTANCE="runagen-ollama"
OLLAMA_ZONE="us-central1-a"
OLLAMA_MACHINE="n1-standard-2"
API_SERVICE="runagen-api"
API_REGION="us-central1"
IMAGE_NAME="gcr.io/${GCP_PROJECT_ID}/${API_SERVICE}"

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

# Create Compute Engine instance for Ollama
echo -e "${YELLOW}Creating Compute Engine instance for Ollama...${NC}"
if gcloud compute instances describe $OLLAMA_INSTANCE --zone=$OLLAMA_ZONE &>/dev/null; then
    echo -e "${YELLOW}⚠ Instance already exists${NC}"
else
    gcloud compute instances create $OLLAMA_INSTANCE \
        --zone=$OLLAMA_ZONE \
        --machine-type=$OLLAMA_MACHINE \
        --image-family=ubuntu-2204-lts \
        --image-project=ubuntu-os-cloud \
        --boot-disk-size=50GB \
        --scopes=default,cloud-platform \
        --tags=ollama,http-server,https-server
    echo -e "${GREEN}✓ Instance created${NC}"
fi

# Wait for instance
echo -e "${YELLOW}Waiting for instance to be ready...${NC}"
sleep 10

# Get instance IP
OLLAMA_IP=$(gcloud compute instances describe $OLLAMA_INSTANCE \
    --zone=$OLLAMA_ZONE \
    --format='get(networkInterfaces[0].networkIP)')

OLLAMA_EXTERNAL_IP=$(gcloud compute instances describe $OLLAMA_INSTANCE \
    --zone=$OLLAMA_ZONE \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo -e "${GREEN}✓ Ollama instance IP: $OLLAMA_IP${NC}"
echo -e "${GREEN}✓ Ollama external IP: $OLLAMA_EXTERNAL_IP${NC}\n"

# Create firewall rule
echo -e "${YELLOW}Creating firewall rule...${NC}"
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

# Install Ollama on instance
echo -e "${YELLOW}Installing Ollama on Compute Engine instance...${NC}"
gcloud compute ssh $OLLAMA_INSTANCE --zone=$OLLAMA_ZONE << 'OLLAMA_SETUP'
    # Update system
    sudo apt-get update -qq
    
    # Install Docker
    if ! command -v docker &> /dev/null; then
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
        newgrp docker
    fi
    
    # Run Ollama
    docker run -d \
        --name ollama \
        -p 11434:11434 \
        -v ollama_data:/root/.ollama \
        --restart unless-stopped \
        ollama/ollama:latest
    
    # Wait for Ollama to start
    sleep 15
    
    # Pull llama3 model
    echo "Pulling llama3 model (this may take 5-10 minutes)..."
    docker exec ollama ollama pull llama3
    
    # Verify
    curl -s http://localhost:11434/api/tags | grep -q llama3 && echo "✓ Ollama ready" || echo "⚠ Ollama setup in progress"
OLLAMA_SETUP

echo -e "${GREEN}✓ Ollama installed and model pulled${NC}\n"

# Build and push Docker image
echo -e "${YELLOW}Building Docker image...${NC}"
docker build -t $IMAGE_NAME:latest -f Dockerfile.cloud .
echo -e "${GREEN}✓ Docker image built${NC}\n"

echo -e "${YELLOW}Pushing image to Container Registry...${NC}"
docker push $IMAGE_NAME:latest
echo -e "${GREEN}✓ Image pushed${NC}\n"

# Deploy to Cloud Run
echo -e "${YELLOW}Deploying to Cloud Run...${NC}"
gcloud run deploy $API_SERVICE \
    --image $IMAGE_NAME:latest \
    --platform managed \
    --region $API_REGION \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 3600 \
    --set-env-vars "ENVIRONMENT=cloud,OLLAMA_URL=http://$OLLAMA_EXTERNAL_IP:11434,OLLAMA_MODEL=llama3,GCP_PROJECT_ID=$GCP_PROJECT_ID,PYTHONUNBUFFERED=1,PYTHONPATH=/app/src" \
    --max-instances 100 \
    --min-instances 0

echo -e "${GREEN}✓ Deployed to Cloud Run${NC}\n"

# Get service URL
API_URL=$(gcloud run services describe $API_SERVICE --region $API_REGION --format='value(status.url)')
echo -e "${GREEN}✓ API URL: $API_URL${NC}\n"

# Display summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Deployment Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Ollama Instance: ${GREEN}$OLLAMA_INSTANCE${NC}"
echo -e "Ollama Zone: ${GREEN}$OLLAMA_ZONE${NC}"
echo -e "Ollama IP: ${GREEN}$OLLAMA_EXTERNAL_IP${NC}"
echo -e "API Service: ${GREEN}$API_SERVICE${NC}"
echo -e "API Region: ${GREEN}$API_REGION${NC}"
echo -e "API URL: ${GREEN}$API_URL${NC}"
echo -e "\n${BLUE}Test Commands:${NC}"
echo -e "  Health: ${GREEN}curl $API_URL/health${NC}"
echo -e "  Analyze: ${GREEN}curl -X POST $API_URL/api/analyze-resume -H 'Content-Type: application/json' -d '{\"resume_text\": \"Python, AWS, Docker\"}'${NC}"
echo -e "\n${BLUE}Monitor Ollama:${NC}"
echo -e "  SSH: ${GREEN}gcloud compute ssh $OLLAMA_INSTANCE --zone=$OLLAMA_ZONE${NC}"
echo -e "  Logs: ${GREEN}docker logs -f ollama${NC}"
echo -e "\n${BLUE}Monitor API:${NC}"
echo -e "  Logs: ${GREEN}gcloud run logs read $API_SERVICE --region $API_REGION --follow${NC}"
echo -e "\n${BLUE}========================================${NC}\n"

echo -e "${GREEN}✅ Deployment complete!${NC}"
echo -e "Your webapp is now live at: ${GREEN}$API_URL${NC}\n"
