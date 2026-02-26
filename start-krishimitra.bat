@echo off
echo ========================================
echo   KrishiMitra Platform Quick Start
echo ========================================
echo.

REM Check if .env exists
if not exist .env (
    echo Creating .env file from .env.example...
    if exist .env.example (
        copy .env.example .env
        echo .env file created. Please edit it with your configuration.
    ) else (
        echo Warning: .env.example not found
    )
    echo.
)

echo Starting KrishiMitra services...
echo.

REM Start API Server
echo [1/2] Starting API Server on http://localhost:8000
start "KrishiMitra API Server" cmd /k "python -m uvicorn src.krishimitra.main:app --reload --host 0.0.0.0 --port 8000"

REM Wait for API to start
timeout /t 3 /nobreak >nul

REM Start Web UI
echo [2/2] Starting Web UI on http://localhost:8080
start "KrishiMitra Web UI" cmd /k "cd ui && python -m http.server 8080"

REM Wait for UI to start
timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo   KrishiMitra is running!
echo ========================================
echo.
echo Access points:
echo   - Web UI:       http://localhost:8080
echo   - API Docs:     http://localhost:8000/docs
echo   - API Health:   http://localhost:8000/api/v1/health
echo.
echo Opening Web UI in your browser...
timeout /t 2 /nobreak >nul

REM Open browser
start http://localhost:8080

echo.
echo Press any key to stop all services...
pause >nul

REM Stop services
echo.
echo Stopping services...
taskkill /FI "WindowTitle eq KrishiMitra*" /F >nul 2>&1
echo Services stopped.
echo.
pause
