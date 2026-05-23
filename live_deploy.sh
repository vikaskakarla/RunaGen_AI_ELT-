#!/bin/bash
# 🚀 RunaGen AI - Master Live Deployment Script
# Automates: ETL -> Training -> API Deployment -> Frontend

echo "================================================================================"
echo "⚡ Starting Live Online Pipeline Deployment"
echo "================================================================================"

# 1. Setup Environment
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/credentials/bigquery-key.json"
export GCP_PROJECT_ID="runagen-ai"

# 2. Step 1: Live ETL (Sync MongoDB to BigQuery)
echo "📥 Syncing fresh data from MongoDB to BigQuery..."
python3 src/etl/mongodb_to_bigquery.py

# 3. Step 2: Automatic Model Retraining (>90% Accuracy)
echo "🧠 Retraining models with high accuracy target..."
python3 src/ml/train_models_advanced_90pct.py

# 4. Step 3: Deploy Backend (FastAPI v2)
echo "🌐 Deploying Backend API..."
# Kill existing API if running
pkill -f "src.api.main_v2_90pct" || true
nohup python3 -m uvicorn src.api.main_v2_90pct:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &

# 5. Step 4: Deploy Frontend
echo "💻 Launching Web Interface..."
cd web && nohup npm run dev > ../logs/web.log 2>&1 &

echo "✅ Live Pipeline is now ONLINE and AUTOMATED!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:8080"
echo "================================================================================"
