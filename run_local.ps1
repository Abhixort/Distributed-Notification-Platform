# PowerShell script to start the Distributed Notification Platform locally
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  Starting Distributed Notification Platform (Local) " -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

# Set local fallback environment defaults if not already set
if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "sqlite+aiosqlite:///./notifications.db"
    $env:DATABASE_SYNC_URL = "sqlite:///./notifications.db"
}

Write-Host "[1/2] Seeding initial database templates & keys..." -ForegroundColor Yellow
.\venv\Scripts\python scripts/seed_data.py

Write-Host "[2/2] Launching FastAPI ASGI Server on http://localhost:8000..." -ForegroundColor Green
Write-Host "Dashboard:  http://localhost:8000/dashboard" -ForegroundColor Magenta
Write-Host "API Docs:   http://localhost:8000/docs" -ForegroundColor Magenta
Write-Host "Metrics:    http://localhost:8000/metrics" -ForegroundColor Magenta

.\venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
