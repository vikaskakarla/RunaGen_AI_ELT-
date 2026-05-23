@echo off
REM Live Pipeline Runner for Windows
REM This script starts the live data pipeline

echo ========================================
echo   Live Data Pipeline - RunaGen AI
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv\" (
    echo WARNING: Virtual environment not found
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update dependencies
echo.
echo Checking dependencies...
pip install -r requirements-live.txt --quiet
if errorlevel 1 (
    echo WARNING: Some dependencies failed to install
    echo Continuing anyway...
)

REM Create logs directory
if not exist "logs\" mkdir logs

REM Parse command line arguments
set MODE=development
set RUN_ONCE=
set LOG_LEVEL=INFO

:parse_args
if "%1"=="" goto end_parse
if /i "%1"=="--production" set MODE=production
if /i "%1"=="--development" set MODE=development
if /i "%1"=="--testing" set MODE=testing
if /i "%1"=="--run-once" set RUN_ONCE=--run-once
if /i "%1"=="--debug" set LOG_LEVEL=DEBUG
shift
goto parse_args
:end_parse

REM Display configuration
echo.
echo ========================================
echo Configuration:
echo   Mode: %MODE%
echo   Log Level: %LOG_LEVEL%
if defined RUN_ONCE (
    echo   Run Mode: Single execution
) else (
    echo   Run Mode: Continuous
)
echo ========================================
echo.

REM Run the pipeline
echo Starting live pipeline...
echo.
python run_live_pipeline.py --mode %MODE% --log-level %LOG_LEVEL% %RUN_ONCE%

REM Check exit code
if errorlevel 1 (
    echo.
    echo ERROR: Pipeline exited with error code %errorlevel%
    pause
    exit /b %errorlevel%
)

echo.
echo Pipeline stopped successfully
pause