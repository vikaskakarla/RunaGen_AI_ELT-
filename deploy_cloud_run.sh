#!/bin/bash

# RunaGen AI - Google Cloud Run Deployment Script
# This script deploys the API to Google Cloud Run with proper configuration

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}RunaGen AI - Cloud Run Deployment${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Configuration
GCP_PROJECT_ID="runagen-ai"
SERVICE_NAME="runagen-api"
REGION="us-central1"
IMAGE_NAME="gcr.io/${GCP_PROJECT_ID}/${SERVICE_NAME}"
MEMORY="2Gi"
CPU="2"
TIMEOUT="3600"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not found. Please install Google Cloud SDK.${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites met${NC}\n"

# Set GCP project
echo -e "${YELLOW}Setting GCP project...${NC}"
gcloud config set project $GCP_PROJECT_ID
echo -e "${GREEN}✓ Project set to $GCP_PROJECT_ID${NC}\n"

# Enable required APIs
echo -e "${YELLOW}Enabling required GCP APIs...${NC}"
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable bigquery.googleapis.com
gcloud services enable storage-api.googleapis.com
gcloud services enable secretmanager.googleapis.com
echo -e "${GREEN}✓ APIs enabled${NC}\n"

# Create/update secrets
echo -e "${YELLOW}Setting up secrets in Secret Manager...${NC}"

# Function to create or update secret
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2
    
    if gcloud secrets describe $secret_name &>/dev/null; then
        echo "  Updating secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets versions add $secret_name --data-file=-
    else
        echo "  Creating secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets create $secret_name --data-file=-
    fi
}

# Read from .env.cloud or prompt user
if [ -f ".env.cloud" ]; then
    echo -e "${GREEN}✓ Found .env.cloud file${NC}"
    source .env.cloud
else
    echo -e "${YELLOW}⚠ .env.cloud not found. Please create it with required secrets.${NC}"
    exit 1
fi

# Create secrets
create_or_update_secret "gemini-api-key" "$GEMINI_API_KEY"
create_or_update_secret "adzuna-app-id" "$ADZUNA_APP_ID"
create_or_update_secret "adzuna-app-key" "$ADZUNA_APP_KEY"
create_or_update_secret "mongo-uri" "$MONGO_URI"

echo -e "${GREEN}✓ Secrets configured${NC}\n"

# Build Docker image
echo -e "${YELLOW}Building Docker image...${NC}"
docker build -t $IMAGE_NAME:latest .
echo -e "${GREEN}✓ Docker image built${NC}\n"

# Push to Container Registry
echo -e "${YELLOW}Pushing image to Container Registry...${NC}"
docker push $IMAGE_NAME:latest
echo -e "${GREEN}✓ Image pushed to $IMAGE_NAME:latest${NC}\n"

# Deploy to Cloud Run
echo -e "${YELLOW}Deploying to Cloud Run...${NC}"
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME:latest \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory $MEMORY \
    --cpu $CPU \
    --timeout $TIMEOUT \
    --set-env-vars "ENVIRONMENT=cloud,GCP_PROJECT_ID=$GCP_PROJECT_ID,PYTHONUNBUFFERED=1,PYTHONPATH=/app/src" \
    --set-secrets "GEMINI_API_KEY=gemini-api-key:latest,ADZUNA_APP_ID=adzuna-app-id:latest,ADZUNA_APP_KEY=adzuna-app-key:latest,MONGO_URI=mongo-uri:latest" \
    --max-instances 100 \
    --min-instances 0

echo -e "${GREEN}✓ Deployment complete${NC}\n"

# Get service URL
echo -e "${YELLOW}Retrieving service URL...${NC}"
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format='value(status.url)')
echo -e "${GREEN}✓ Service URL: $SERVICE_URL${NC}\n"

# Display deployment info
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Deployment Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Service Name: ${GREEN}$SERVICE_NAME${NC}"
echo -e "Region: ${GREEN}$REGION${NC}"
echo -e "Image: ${GREEN}$IMAGE_NAME:latest${NC}"
echo -e "Memory: ${GREEN}$MEMORY${NC}"
echo -e "CPU: ${GREEN}$CPU${NC}"
echo -e "URL: ${GREEN}$SERVICE_URL${NC}"
echo -e "\n${BLUE}Health Check:${NC}"
echo -e "  ${GREEN}curl $SERVICE_URL/health${NC}"
echo -e "\n${BLUE}Analyze Resume:${NC}"
echo -e "  ${GREEN}curl -X POST $SERVICE_URL/api/analyze-resume${NC}"
echo -e "\n${BLUE}View Logs:${NC}"
echo -e "  ${GREEN}gcloud run logs read $SERVICE_NAME --region $REGION --limit 50 --follow${NC}"
echo -e "\n${BLUE}========================================${NC}\n"

echo -e "${GREEN}✅ Deployment successful!${NC}"
echo -e "API is now available at: ${GREEN}$SERVICE_URL${NC}\n"
