#!/bin/bash
echo "Starting TIS Backend on port 8000..."
cd "$(dirname "$0")" && python -m uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

echo "Starting TIS Frontend on port 3000..."
cd "$(dirname "$0")/frontend" && npm run dev &
FRONTEND_PID=$!

echo ""
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "Press Ctrl+C to stop both"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
