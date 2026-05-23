@echo off
REM RunaGen AI - One-Command Startup Script (Windows Version)
REM Version 3.0 - With Live Data Pipeline

echo 🚀 Starting RunaGen AI Project...
echo ======================================
echo Features:
echo   ✅ Core: Resume Analysis (92.70%% accuracy)
echo   ✅ Phase 3: Real-time Job Scraping
echo   ✅ Phase 4: Learning Path Generation
echo   ✅ Phase 5: Skill Trend Analysis
echo   ✅ Phase 6: Resume Optimization
echo   ✅ LIVE PIPELINE: Auto-refresh on startup
echo ======================================

REM Install critical dependencies
echo 📦 Checking dependencies...
python -m pip install -q db-dtypes==1.1.1 >nul 2>&1
python -m pip install -q apscheduler >nul 2>&1
echo ✓ Dependencies checked

REM Create logs directory if needed
if not exist "logs\" mkdir logs

REM Kill any existing API process on port 8000
echo Checking for existing processes on port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do (
    echo Stopping existing process on port 8000 (PID: %%a)...
    taskkill /PID %%a /F >nul 2>&1
)

REM Check if Ollama is available (optional)
echo Checking Ollama availability...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ Ollama is available
) else (
    echo ⚠ Ollama not available - will use fallback methods
)

REM Start the unified FastAPI server with Phase 3-6 features + Live Pipeline
echo Starting RunaGen AI API v3 with Live Pipeline...
echo ⏳ Initializing server (pipeline will auto-check data freshness)...
echo.
echo   📡 Live Dashboard: http://localhost:8000/live-dashboard.html
echo   🏠 Resume Analyzer: http://localhost:8000
echo.

python src/api/main.py

echo.
echo ======================================
echo Press Ctrl+C to stop the project
echo ======================================