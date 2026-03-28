#!/bin/bash
set -e

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
MAX_RETRIES=30
RETRY_INTERVAL=2

check_backend() {
    echo "Checking backend at $BACKEND_URL..."
    for i in $(seq 1 $MAX_RETRIES); do
        if curl -sf "$BACKEND_URL/health" > /dev/null 2>&1; then
            echo "Backend is healthy"
            return 0
        fi
        echo "Attempt $i/$MAX_RETRIES: Backend not ready, waiting..."
        sleep $RETRY_INTERVAL
    done
    echo "Backend health check failed"
    return 1
}

check_frontend() {
    echo "Checking frontend at $FRONTEND_URL..."
    for i in $(seq 1 $MAX_RETRIES); do
        if curl -sf "$FRONTEND_URL/health" > /dev/null 2>&1; then
            echo "Frontend is healthy"
            return 0
        fi
        echo "Attempt $i/$MAX_RETRIES: Frontend not ready, waiting..."
        sleep $RETRY_INTERVAL
    done
    echo "Frontend health check failed"
    return 1
}

case "${1:-all}" in
    backend)
        check_backend
        ;;
    frontend)
        check_frontend
        ;;
    all)
        check_backend || exit 1
        check_frontend
        ;;
    *)
        echo "Usage: $0 {backend|frontend|all}"
        exit 1
        ;;
esac