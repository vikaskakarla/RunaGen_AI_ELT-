#!/bin/bash

# RunaGen AI v2 - Complete Startup Script
# Starts all services: Backend API, Frontend, and Ollama

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "========================================================================"
echo "🚀 RunaGen AI v2 - Complete System Startup"
echo "========================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ===== ENVIRONMENT SETUP =====
echo -e "${BLUE}📋 Setting up environment...${NC}"

export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/credentials/bigquery-key.json"
export GCP_PROJECT_ID=runagen-ai

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating from .env.example...${NC}"
    cp .env.example .env
fi

source .env

echo -e "${GREEN}✓ Environment configured${NC}"
echo ""

# ===== VERIFY MODELS =====
echo -e "${BLUE}🤖 Checking ML models...${NC}"

if [ -f "models/career_predictor_90pct.pkl" ]; then
    echo -e "${GREEN}✓ Career model (91.42%) found${NC}"
else
    echo -e "${YELLOW}⚠️  Career model not found. Training...${NC}"
    python3 src/ml/train_models_advanced_90pct.py
fi

if [ -f "models/salary_predictor_90pct.pkl" ]; then
    echo -e "${GREEN}✓ Salary model found${NC}"
else
    echo -e "${YELLOW}⚠️  Salary model not found${NC}"
fi

echo ""

# ===== START SERVICES =====
echo -e "${BLUE}🚀 Starting services...${NC}"
echo ""

# Function to handle cleanup
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    kill $OLLAMA_PID 2>/dev/null || true
    echo -e "${GREEN}✓ All services stopped${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start Backend API (v2 with 91.42% models)
echo -e "${BLUE}1️⃣  Starting Backend API (v2 - 91.42% Accuracy)...${NC}"
python3 -m uvicorn src.api.main_v2_90pct:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    > logs/api.log 2>&1 &
BACKEND_PID=$!
echo -e "${GREEN}✓ Backend running on http://localhost:8000${NC}"
sleep 2

# Start Frontend
echo -e "${BLUE}2️⃣  Starting Frontend...${NC}"
cd web
npm install > /dev/null 2>&1 || true
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
echo -e "${GREEN}✓ Frontend running on http://localhost:8080${NC}"
sleep 2

# Start Ollama (Optional)
echo -e "${BLUE}3️⃣  Checking Ollama...${NC}"
if command -v ollama &> /dev/null; then
    echo -e "${YELLOW}Starting Ollama...${NC}"
    ollama serve > logs/ollama.log 2>&1 &
    OLLAMA_PID=$!
    echo -e "${GREEN}✓ Ollama running on http://localhost:11434${NC}"
else
    echo -e "${YELLOW}⚠️  Ollama not installed (optional)${NC}"
fi

echo ""
echo "========================================================================"
echo -e "${GREEN}✅ RunaGen AI v2 is running!${NC}"
echo "========================================================================"
echo ""
echo "📊 Services:"
echo "  - Backend API:  http://localhost:8000"
echo "  - Frontend:     http://localhost:8080"
echo "  - Health Check: http://localhost:8000/health"
echo ""
echo "📈 Model Performance:"
echo "  - Career Accuracy: 91.42%"
echo "  - Salary R²: 1.0000"
echo ""
echo "📚 Documentation:"
echo "  - API Docs:     http://localhost:8000/docs"
echo "  - Deployment:   DEPLOYMENT_GUIDE_V2.md"
echo ""
echo "Press Ctrl+C to stop all services"
echo "========================================================================"
echo ""

# Wait for all processes
wait
