#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

# Optional: seed data if INIT_DATA=true
if [ "${INIT_DATA:-false}" = "true" ]; then
    echo "Seeding initial data..."
    python seed_db.py
fi

echo "Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
