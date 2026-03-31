# =======================
# Stage 1: Builder
# =======================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies for compiled Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies to isolated location
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# =======================
# Stage 2: Runtime
# =======================
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser alembic.ini /app/alembic.ini
COPY --chown=appuser:appuser alembic/env.py /app/alembic/env.py
COPY --chown=appuser:appuser alembic/versions /app/alembic/versions
COPY --chown=appuser:appuser app/ /app/app/
COPY --chown=appuser:appuser requirements.txt /app/requirements.txt

# Ensure /tmp/tis_uploads writable by appuser via chown (named volume mounts over it)
# chown as root here since volume mount will override dir ownership at runtime
RUN mkdir -p /tmp/tis_uploads && chown appuser:appuser /tmp/tis_uploads

# Set environment
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER appuser

# Health check using curl (installed in runtime stage)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Run migrations then start server
CMD ["sh", "-c", "mkdir -p /tmp/tis_uploads && alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
