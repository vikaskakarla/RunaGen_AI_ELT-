#!/bin/bash
# RunaGen AI - One-Command Startup Script
# Version 2.0 - With Phase 3-6 Features

echo "🚀 Starting RunaGen AI Project..."
echo "======================================"
echo "Features:"
echo "  ✅ Core: Resume Analysis (91.42% accuracy)"
echo "  ✅ Phase 3: Real-time Job Scraping"
echo "  ✅ Phase 4: Learning Path Generation"
echo "  ✅ Phase 5: Skill Trend Analysis"
echo "  ✅ Phase 6: Resume Optimization"
echo "======================================"

# Install critical dependencies
echo "📦 Checking dependencies..."
python3 -m pip install -q db-dtypes==1.1.1 2>/dev/null
echo "✓ Dependencies checked"

# Kill any existing API process on port 8000
PORT=8000
PID=$(lsof -ti :$PORT)
if [ ! -z "$PID" ]; then
    echo "Stopping existing process on port $PORT (PID: $PID)..."
    kill -9 $PID
fi

# Check and start Ollama
echo "Checking Ollama..."
if ! pgrep ollama > /dev/null; then
    echo "Starting Ollama..."
    ollama serve > /dev/null 2>&1 &
    # Allow some time for Ollama to start
    for i in {1..10}; do
        if curl -s http://localhost:11434/api/tags > /dev/null; then
            break
        fi
        sleep 1
    done
fi

# Ensure llama3 model is available
if ! ollama list | grep -q "llama3"; then
    echo "Pulling llama3 model (this may take a while)..."
    ollama pull llama3
fi

# Start the unified FastAPI server with Phase 3-6 features
echo "Starting RunaGen AI API v2 with all features..."
python3 src/api/main.py &
API_PID=$!

# Wait for server to be ready
echo "Waiting for server to initialize..."
MAX_RETRIES=300
COUNT=0
while ! curl -s http://localhost:8000/health > /dev/null; do
    sleep 1
    COUNT=$((COUNT + 1))
    if [ $COUNT -ge $MAX_RETRIES ]; then
        echo "❌ Server failed to start within $MAX_RETRIES seconds. Check logs."
        exit 1
    fi
    # Print a status dot every 5 seconds
    if [ $((COUNT % 5)) -eq 0 ]; then
        echo "Still waiting for server... ($COUNT/$MAX_RETRIES)"
    fi
done

echo "✅ Server is healthy!"
echo "🔗 Access RunaGen AI at: http://localhost:8000"
echo ""
echo "Available Features:"
echo "  📄 Resume Analysis: /api/analyze-resume"
echo "  🔍 Job Market: /api/jobs/scrape"
echo "  📚 Learning Path: /api/learning-path"
echo "  📈 Skill Trends: /api/skill-trends/trending"
echo "  ✨ Resume Optimizer: /api/resume/optimize"
echo ""

# Open in browser
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:8000
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open http://localhost:8000
fi

echo "======================================"
echo "Press Ctrl+C to stop the project"
echo "======================================"

# Wait for API process
trap "echo ''; echo 'Stopping RunaGen AI...'; kill $API_PID; exit" INT
wait $API_PID
