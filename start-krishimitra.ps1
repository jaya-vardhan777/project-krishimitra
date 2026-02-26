# KrishiMitra Quick Start Script for Windows
# This script starts both the API server and Web UI

Write-Host "🌾 Starting KrishiMitra Platform..." -ForegroundColor Green
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python not found. Please install Python 3.9+ first." -ForegroundColor Red
    exit 1
}

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "⚠ .env file not found. Creating from .env.example..." -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "✓ .env file created. Please edit it with your configuration." -ForegroundColor Green
    } else {
        Write-Host "✗ .env.example not found. Please create .env manually." -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Starting services..." -ForegroundColor Cyan
Write-Host ""

# Start API Server in a new window
Write-Host "1. Starting API Server on http://localhost:8000" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python -m uvicorn src.krishimitra.main:app --reload --host 0.0.0.0 --port 8000"

# Wait a bit for the API to start
Start-Sleep -Seconds 3

# Start Web UI in a new window
Write-Host "2. Starting Web UI on http://localhost:8080" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd ui; python -m http.server 8080"

# Wait a bit for the UI to start
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "✓ KrishiMitra is starting!" -ForegroundColor Green
Write-Host ""
Write-Host "Access points:" -ForegroundColor Yellow
Write-Host "  • Web UI:          http://localhost:8080" -ForegroundColor White
Write-Host "  • API Docs:        http://localhost:8000/docs" -ForegroundColor White
Write-Host "  • API Health:      http://localhost:8000/api/v1/health" -ForegroundColor White
Write-Host ""
Write-Host "Opening Web UI in your browser..." -ForegroundColor Cyan
Start-Sleep -Seconds 2

# Open browser
Start-Process "http://localhost:8080"

Write-Host ""
Write-Host "Press any key to stop all services..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# Cleanup (stop processes)
Write-Host ""
Write-Host "Stopping services..." -ForegroundColor Red
Get-Process | Where-Object {$_.MainWindowTitle -like "*uvicorn*" -or $_.MainWindowTitle -like "*http.server*"} | Stop-Process -Force
Write-Host "✓ Services stopped." -ForegroundColor Green
