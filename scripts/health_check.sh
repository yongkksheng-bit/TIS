#!/bin/bash
set -e
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
MAX_RETRIES=30
RETRY_INTERVAL=2

echo "Checking backend at $BACKEND_URL..."
for i in $(seq 1 $MAX_RETRIES); do
    if curl -sf "$BACKEND_URL/health" > /dev/null 2>&1; then
        echo "Backend is healthy"
        exit 0
    fi
    echo "Attempt $i/$MAX_RETRIES: Backend not ready, waiting..."
    sleep $RETRY_INTERVAL
done
echo "Backend health check failed"
exit 1
