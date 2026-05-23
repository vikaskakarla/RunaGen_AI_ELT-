#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Progress bar function
show_progress() {
    local current=$1
    local total=$2
    local width=50
    local percentage=$((current * 100 / total))
    local filled=$((width * current / total))
    
    printf "\r${BLUE}["
    printf "%${filled}s" | tr ' ' '='
    printf "%$((width - filled))s" | tr ' ' '-'
    printf "]${NC} ${percentage}%% ($current/$total)"
}

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}  🚀 RunaGen AI - Google Cloud Run Deployment${NC}           ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Set project
echo -e "${YELLOW}Step 1/6: Setting GCP Project${NC}"
show_progress 1 6
gcloud config set project runagen-ai > /dev/null 2>&1
echo ""
echo -e "${GREEN}✓ Project set to runagen-ai${NC}"
echo ""

# Step 2: Enable APIs
echo -e "${YELLOW}Step 2/6: Enabling Required APIs${NC}"
show_progress 2 6
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com > /dev/null 2>&1
echo ""
echo -e "${GREEN}✓ APIs enabled${NC}"
echo ""

# Step 3: Configure Docker
echo -e "${YELLOW}Step 3/6: Configuring Docker Authentication${NC}"
show_progress 3 6
gcloud auth configure-docker gcr.io > /dev/null 2>&1
echo ""
echo -e "${GREEN}✓ Docker configured${NC}"
echo ""

# Step 4: Build and push
echo -e "${YELLOW}Step 4/6: Building Docker Image${NC}"
show_progress 4 6
echo ""
gcloud builds submit --tag gcr.io/runagen-ai/runagen-api:latest . --quiet
echo ""
echo -e "${GREEN}✓ Docker image built and pushed${NC}"
echo ""

# Step 5: Deploy to Cloud Run
echo -e "${YELLOW}Step 5/6: Deploying to Cloud Run${NC}"
show_progress 5 6
echo ""
gcloud run deploy runagen-api \
  --image gcr.io/runagen-ai/runagen-api:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 3600 \
  --set-env-vars "GCP_PROJECT_ID=runagen-ai,PYTHONUNBUFFERED=1,PYTHONPATH=/app/src" \
  --quiet
echo ""
echo -e "${GREEN}✓ Service deployed${NC}"
echo ""

# Step 6: Get service URL
echo -e "${YELLOW}Step 6/6: Getting Service URL${NC}"
show_progress 6 6
SERVICE_URL=$(gcloud run services describe runagen-api --region us-central1 --format='value(status.url)')
echo ""
echo -e "${GREEN}✓ Service URL retrieved${NC}"
echo ""

# Final summary
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}  ✅ Deployment Successful!${NC}                              ${GREEN}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}📊 Service Details:${NC}"
echo -e "  ${BLUE}URL:${NC}        $SERVICE_URL"
echo -e "  ${BLUE}API Docs:${NC}   $SERVICE_URL/docs"
echo -e "  ${BLUE}Health:${NC}     $SERVICE_URL/health"
echo -e "  ${BLUE}Region:${NC}     us-central1"
echo -e "  ${BLUE}Memory:${NC}     2 GB"
echo -e "  ${BLUE}CPU:${NC}        2"
echo ""
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo -e "  1. Test the API: curl $SERVICE_URL/health"
echo -e "  2. View logs: gcloud run logs read runagen-api --region us-central1"
echo -e "  3. Monitor: gcloud run services describe runagen-api --region us-central1"
echo ""
