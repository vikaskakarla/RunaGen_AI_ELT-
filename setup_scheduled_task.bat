@echo off
REM ════════════════════════════════════════════════════════════
REM   RunaGen AI — Windows Task Scheduler Setup
REM   Sets up automatic background data pipeline runs
REM ════════════════════════════════════════════════════════════
REM
REM   This creates a Windows Scheduled Task that runs the data
REM   pipeline every 6 hours, even when you're not using the app.
REM
REM   When you open the app later, data will already be fresh!
REM
REM   To remove: schtasks /delete /tn "RunaGen_Pipeline" /f
REM ════════════════════════════════════════════════════════════

echo.
echo ════════════════════════════════════════════════════════
echo   RunaGen AI — Scheduled Pipeline Setup
echo ════════════════════════════════════════════════════════
echo.
echo   This will create a Windows Scheduled Task that runs
echo   the data pipeline every 6 hours in the background.
echo.
echo   Benefits:
echo     - Data stays fresh even when you don't use the app
echo     - Server starts faster (data already up to date)
echo     - ML models stay trained on latest data
echo.

set /p CONFIRM="Do you want to set this up? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo Cancelled.
    pause
    exit /b 0
)

REM Get the current directory (project root)
set PROJECT_DIR=%~dp0
set PYTHON_PATH=python

REM Check if venv exists
if exist "%PROJECT_DIR%venv_runagen\Scripts\python.exe" (
    set PYTHON_PATH=%PROJECT_DIR%venv_runagen\Scripts\python.exe
    echo Using venv Python: %PYTHON_PATH%
) else if exist "%PROJECT_DIR%venv\Scripts\python.exe" (
    set PYTHON_PATH=%PROJECT_DIR%venv\Scripts\python.exe
    echo Using venv Python: %PYTHON_PATH%
) else (
    echo Using system Python
)

REM Create the scheduled task
echo.
echo Creating scheduled task...
echo.

schtasks /create /tn "RunaGen_Pipeline" ^
    /tr "\"%PYTHON_PATH%\" \"%PROJECT_DIR%run_pipeline_once.py\" --limit 200" ^
    /sc HOURLY /mo 6 ^
    /st 00:00 ^
    /f ^
    /rl HIGHEST

if %errorlevel% equ 0 (
    echo.
    echo ════════════════════════════════════════════════════════
    echo   ✅ SUCCESS! Scheduled task created.
    echo.
    echo   Task Name:  RunaGen_Pipeline
    echo   Schedule:   Every 6 hours
    echo   Script:     %PROJECT_DIR%run_pipeline_once.py
    echo   Logs:       %PROJECT_DIR%logs\pipeline_scheduled_run.log
    echo.
    echo   To check status:  schtasks /query /tn "RunaGen_Pipeline"
    echo   To run now:       schtasks /run /tn "RunaGen_Pipeline"
    echo   To remove:        schtasks /delete /tn "RunaGen_Pipeline" /f
    echo ════════════════════════════════════════════════════════
) else (
    echo.
    echo ❌ Failed to create scheduled task.
    echo    Try running this script as Administrator.
)

echo.
pause
