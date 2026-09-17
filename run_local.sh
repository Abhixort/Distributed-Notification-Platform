#!/usr/bin/env bash
set -e

echo "====================================================="
echo "  Starting Distributed Notification Platform (Local) "
echo "====================================================="

export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///./notifications.db}"
export DATABASE_SYNC_URL="${DATABASE_SYNC_URL:-sqlite:///./notifications.db}"

echo "[1/2] Seeding initial database templates & keys..."
python scripts/seed_data.py

echo "[2/2] Launching FastAPI ASGI Server on http://localhost:8000..."
echo "Dashboard:  http://localhost:8000/dashboard"
echo "API Docs:   http://localhost:8000/docs"
echo "Metrics:    http://localhost:8000/metrics"

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
