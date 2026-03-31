#!/bin/bash
# ============================================
# TIS - Docker Compose Mode (recommended)
# ============================================
echo "Starting TIS with Docker Compose..."
cd "$(dirname "$0")"

docker compose up -d

echo ""
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "Press 'docker compose down' to stop"
