#!/bin/bash

echo "🔧 Installing RunaGen AI ML-ETL Project Dependencies..."
echo "=========================================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✅ Python version: $(python3 --version)"
echo ""

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed. Please install pip."
    exit 1
fi

echo "✅ pip version: $(pip3 --version)"
echo ""

# Upgrade pip
echo "📦 Upgrading pip..."
pip3 install --upgrade pip setuptools wheel
echo ""

# Install requirements
echo "📦 Installing dependencies from requirements.txt..."
pip3 install -r requirements.txt

# Verify critical packages
echo ""
echo "🔍 Verifying critical packages..."
echo ""

# Check pandas-gbq
if python3 -c "import pandas_gbq; print(f'✅ pandas-gbq {pandas_gbq.__version__} installed')" 2>/dev/null; then
    echo "   pandas-gbq: OK"
else
    echo "   ⚠️  pandas-gbq not found. Installing..."
    pip3 install pandas-gbq==0.26.1
fi

# Check google-cloud-bigquery
if python3 -c "import google.cloud.bigquery; print(f'✅ google-cloud-bigquery installed')" 2>/dev/null; then
    echo "   google-cloud-bigquery: OK"
else
    echo "   ❌ google-cloud-bigquery not found"
fi

# Check pymongo
if python3 -c "import pymongo; print(f'✅ pymongo {pymongo.__version__} installed')" 2>/dev/null; then
    echo "   pymongo: OK"
else
    echo "   ❌ pymongo not found"
fi

# Check pandas
if python3 -c "import pandas; print(f'✅ pandas {pandas.__version__} installed')" 2>/dev/null; then
    echo "   pandas: OK"
else
    echo "   ❌ pandas not found"
fi

echo ""
echo "=========================================================="
echo "✅ Dependency installation complete!"
echo "=========================================================="
echo ""
echo "Next steps:"
echo "1. Ensure .env file is configured with MongoDB and BigQuery credentials"
echo "2. Run: python3 run_etl.py"
echo ""
