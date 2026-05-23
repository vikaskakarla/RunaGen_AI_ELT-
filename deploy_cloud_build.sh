#!/bin/bash
# RunaGen AI - Cloud Build Deployment Script
# This script uses Google Cloud Build to build and push the image, 
# then deploys it to Cloud Run. No local Docker required.

set -e

# Configuration
PROJECT_ID="runagen-ai"
SERVICE_NAME="runagen-api"
REGION="us-central1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

echo "🚀 RunaGen AI - Deploying to Google Cloud Run via Cloud Build"
echo "==========================================================="

# Step 1: Submit build to Google Cloud Build
echo "🏗️  Building Docker image using Cloud Build (Optimized with CPU-only torch)..."
gcloud builds submit --tag "$IMAGE_NAME" --timeout=1800 .

# Step 2: Deploy to Cloud Run
echo "🌐 Deploying to Cloud Run (Service: $SERVICE_NAME)..."

gcloud run deploy "$SERVICE_NAME" \
    --image "$IMAGE_NAME" \
    --platform managed \
    --region "$REGION" \
    --allow-unauthenticated \
    --memory 4Gi \
    --cpu 2 \
    --timeout 3600 \
    --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/bigquery-key.json,OLLAMA_URL=http://localhost:11434/api/generate,OLLAMA_MODEL=llama3" \
    --set-secrets "MONGO_URI=mongo-uri:latest,ADZUNA_APP_ID=adzuna-app-id:latest,ADZUNA_APP_KEY=adzuna-app-key:latest,/app/credentials/bigquery-key.json=bigquery-key:latest"


echo "✅ Deployment successful!"

# Get Service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format 'value(status.url)')
echo "📍 Service URL: $SERVICE_URL"
echo "📚 API Docs: $SERVICE_URL/docs"
echo "==========================================================="
