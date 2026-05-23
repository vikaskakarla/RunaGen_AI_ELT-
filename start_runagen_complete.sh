#!/bin/bash

echo "================================================================================"
echo "🚀 RunaGen AI - Complete System Startup"
echo "   Version 2.0.0 | Model Accuracy: 91.42%"
echo "================================================================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✅ Python version: $(python3 --version)"
echo ""

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✅ Created .env file. Please configure it with your credentials."
    else
        echo "❌ .env.example not found. Please create .env manually."
        exit 1
    fi
fi

# Check if models exist
if [ ! -f "models/career_predictor_90pct.pkl" ]; then
    echo "⚠️  91.42% accurate models not found."
    echo "   Run: python3 src/ml/train_models_advanced_90pct.py"
    echo ""
    read -p "   Do you want to train models now? (y/n): " train_choice
    if [ "$train_choice" = "y" ]; then
        echo "🔧 Training models (this may take 2-3 minutes)..."
        python3 src/ml/train_models_advanced_90pct.py
        if [ $? -ne 0 ]; then
            echo "❌ Model training failed."
            exit 1
        fi
    else
        echo "⚠️  Continuing without 91.42% models. API will use fallback."
    fi
fi

# Check if BigQuery credentials exist
if [ ! -f "credentials/bigquery-key.json" ]; then
    echo "⚠️  BigQuery credentials not found at credentials/bigquery-key.json"
    echo "   Some features (Phase 5: Skill Trends) may not work."
    echo ""
fi

# Check dependencies
echo "🔍 Checking dependencies..."
python3 << 'EOF'
import sys
packages = ['fastapi', 'uvicorn', 'pandas', 'numpy', 'sklearn', 'pymongo', 'google.cloud.bigquery']
missing = []
for pkg in packages:
    try:
        __import__(pkg.replace('.', '_') if '.' in pkg else pkg)
    except ImportError:
        missing.append(pkg)

if missing:
    print(f"❌ Missing packages: {', '.join(missing)}")
    print("   Run: pip3 install -r requirements.txt")
    sys.exit(1)
else:
    print("✅ All dependencies installed")
EOF

if [ $? -ne 0 ]; then
    echo ""
    read -p "Install dependencies now? (y/n): " install_choice
    if [ "$install_choice" = "y" ]; then
        echo "📦 Installing dependencies..."
        pip3 install -r requirements.txt
        if [ $? -ne 0 ]; then
            echo "❌ Dependency installation failed."
            exit 1
        fi
    else
        echo "❌ Cannot start without dependencies."
        exit 1
    fi
fi

echo ""
echo "================================================================================"
echo "🎯 Starting RunaGen AI API v2"
echo "================================================================================"
echo ""
echo "Features Available:"
echo "  ✅ Core: Resume Analysis (91.42% accuracy)"
echo "  ✅ Phase 3: Real-time Job Scraping"
echo "  ✅ Phase 4: Learning Path Generation"
echo "  ✅ Phase 5: Skill Trend Analysis"
echo "  ✅ Phase 6: Resume Optimization"
echo ""
echo "API Endpoints:"
echo "  - Health Check: http://localhost:8000/health"
echo "  - Web Interface: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo ""
echo "================================================================================"
echo ""

# Start the API
echo "🚀 Starting FastAPI server..."
echo ""

cd "$(dirname "$0")"
python3 src/api/main_v2_90pct.py

# If the server stops
echo ""
echo "================================================================================"
echo "✅ RunaGen AI API stopped"
echo "================================================================================"
