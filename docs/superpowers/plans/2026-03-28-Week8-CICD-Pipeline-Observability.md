# Week 8: CI/CD Pipeline & Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement GitHub Actions CI/CD pipeline with automated testing and Docker build, plus production-grade structured logging (structlog) and Sentry exception monitoring for both backend and frontend.

**Architecture:**
- `.github/workflows/production.yml` — GitHub Actions workflow with two jobs: `test` (services + pytest + npm build) and `deploy` (docker build + simulate SSH deploy)
- `app/core/logger.py` — structlog wrapper with JSON output, request_id injection, duration and status_code capture
- `app/main.py` — inject structured logging middleware, initialize Sentry
- `frontend/src/main.ts` — initialize Sentry for Vue with error tracking
- Sentry configured with mock DSN, ignores HTTP 400 (business logic errors), reports all uncaught 500s

**Tech Stack:** GitHub Actions, Docker Compose, structlog, Sentry Python SDK, Sentry Vue SDK, pytest, npm

---

## File Structure

```
D:\tis_project\
  .github/
    workflows/
      production.yml         # CREATE — CI/CD pipeline
  app/
    core/
      logger.py              # CREATE — structlog wrapper
    main.py                  # MODIFY — add logger middleware + Sentry init
  scripts/
    simulate_deploy.sh       # CREATE — simulated production deploy script
  requirements.txt           # MODIFY — add sentry-sdk
  .env.example                # MODIFY — add SENTRY_DSN, SENTRY_ENV vars
  frontend/
    package.json              # MODIFY — add @sentry/vue
    src/
      main.ts                # MODIFY — init Sentry
```

---

## Task 1: CI/CD 自动化流水线

**Files:**
- Create: `.github/workflows/production.yml`
- Create: `scripts/simulate_deploy.sh`

### `.github/workflows/production.yml`

Create `D:\tis_project\.github\workflows\production.yml`:

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [master, main]
  pull_request:
    branches: [master, main]

env:
  PYTHON_VERSION: '3.11'
  NODE_VERSION: '20'
  POSTGRES_DB: tis_test
  POSTGRES_USER: tis
  POSTGRES_PASSWORD: tis
  POSTGRES_HOST: localhost

jobs:
  # ── Job 1: Test ──────────────────────────────────────────────────────
  test:
    name: Test Suite
    runs-on: ubuntu-latest

    services:
      postgres:
        image: pgvector/pgvector:pg15
        env:
          POSTGRES_DB: ${{ env.POSTGRES_DB }}
          POSTGRES_USER: ${{ env.POSTGRES_USER }}
          POSTGRES_PASSWORD: ${{ env.POSTGRES_PASSWORD }}
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 3

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python ${{ env.PYTHON_VERSION }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install Python dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov

      - name: Set up Node.js ${{ env.NODE_VERSION }}
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Pre-build frontend (type check + build)
        run: |
          cd frontend
          npm ci --prefer-offline
          npm run build
        env:
          VITE_USE_MOCK: "false"
          VITE_API_BASE_URL: "/api"

      - name: Run backend tests (Week 3 + 4 + 5)
        run: |
          python -m pytest tests/week3/ tests/week4/ tests/week5/ \
            -v --tb=short --maxfail=1
        env:
          DATABASE_URL: postgresql://${{ env.POSTGRES_USER }}:${{ env.POSTGRES_PASSWORD }}@${{ env.POSTGRES_HOST }}:5432/${{ env.POSTGRES_DB }}
          REDIS_URL: redis://localhost:6379/0

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: .pytest_cache/
          retention-days: 7

  # ── Job 2: Deploy (simulated) ────────────────────────────────────────
  deploy:
    name: Deploy (Simulated)
    runs-on: ubuntu-latest
    needs: test
    if: github.event_name == 'push' && (github.ref == 'refs/heads/master' || github.ref == 'refs/heads/main')

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Docker Hub (mock)
        run: echo "DOCKER_TOKEN=mock" >> $GITHUB_ENV

      - name: Build Docker images
        run: |
          docker compose build --no-cache backend frontend

      - name: Save Docker images as artifact
        run: |
          docker save -o docker-images.tar \
            tis_backend tis_frontend tis_db tis_redis tis_minio

      - name: Upload Docker images artifact
        uses: actions/upload-artifact@v4
        with:
          name: docker-images
          path: docker-images.tar
          retention-days: 1

      - name: Simulate SSH deployment
        run: |
          chmod +x scripts/simulate_deploy.sh
          ./scripts/simulate_deploy.sh
        env:
          DEPLOY_SERVER: ${{ secrets.DEPLOY_SERVER || 'localhost' }}
          DEPLOY_USER: ${{ secrets.DEPLOY_USER || 'root' }}

      - name: Health check after deploy
        run: |
          for i in $(seq 1 30); do
            if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
              echo "Backend healthy after deploy"
              exit 0
            fi
            echo "Attempt $i/30: waiting for backend..."
            sleep 2
          done
          echo "Health check failed"
          exit 1
```

### `scripts/simulate_deploy.sh`

Create `D:\tis_project\scripts\simulate_deploy.sh`:

```bash
#!/bin/bash
# Simulates a production SSH deployment
# In real CI/CD, this would:
#   1. Copy docker-images.tar to production server
#   2. Load images: docker load -i docker-images.tar
#   3. Run: docker compose -f docker-compose.prod.yml up -d
#   4. Run: docker exec backend alembic upgrade head
#   5. Smoke test: curl http://localhost:8000/health

set -e

SERVER="${DEPLOY_SERVER:-localhost}"
USER="${DEPLOY_USER:-root}"

echo "============================================"
echo "  Simulated Production Deploy"
echo "============================================"
echo "Target server: ${USER}@${SERVER}"
echo ""
echo "[1/4] Uploading Docker images (simulated)..."
sleep 1
echo "      ✓ docker-images.tar ready (mock step)"

echo "[2/4] Loading Docker images (simulated)..."
sleep 1
echo "      ✓ Images loaded into registry (mock step)"

echo "[3/4] Running docker compose up -d (simulated)..."
sleep 1
echo "      ✓ Services started: backend, frontend, db, redis, minio (mock step)"

echo "[4/4] Running database migrations..."
sleep 1
echo "      ✓ alembic upgrade head (mock step)"

echo ""
echo "============================================"
echo "  🎉 Deploy simulation complete!"
echo "============================================"
echo ""
echo "  NOTE: This is a SIMULATED deploy."
echo "  In production, DEPLOY_SERVER and DEPLOY_USER"
echo "  secrets would be configured in GitHub."
echo ""
echo "  To enable real deploys:"
echo "  1. Add secrets: DEPLOY_SERVER, DEPLOY_USER, DEPLOY_SSH_KEY"
echo "  2. Replace simulate_deploy.sh with real SSH/SCP commands"
echo "  3. Use docker-compose.prod.yml with production configs"
echo ""

exit 0
```

### Commit

```bash
git add .github/workflows/production.yml scripts/simulate_deploy.sh
git commit -m "feat(week8): add GitHub Actions CI/CD pipeline with test and simulated deploy jobs"
```

---

## Task 2: 生产级可观测性与日志

**Files:**
- Create: `app/core/logger.py`
- Modify: `app/main.py`
- Modify: `requirements.txt`
- Modify: `.env.example`
- Modify: `frontend/package.json`
- Modify: `frontend/src/main.ts`

### `app/core/logger.py`

Create `D:\tis_project\app\core\logger.py`:

```python
"""Structured logging via structlog — outputs JSON for ELK/Aliyun Log compatibility."""
import logging
import sys
import time
import uuid
from typing import Optional

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ── structlog configuration ────────────────────────────────────────────────


def add_app_context(logger, method_name, event_dict):
    """Add global app context to every log event."""
    event_dict["app"] = "tis"
    event_dict["version"] = "1.0.0"
    return event_dict


def rename_event_key(logger, method_name, event_dict):
    """Rename 'event' key to 'message' for standard JSON field name."""
    if "event" in event_dict:
        event_dict["message"] = event_dict.pop("event")
    return event_dict


structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        rename_event_key,
        add_app_context,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


# ── Request logging middleware ──────────────────────────────────────────────


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    - Assigns a unique request_id to every incoming request
    - Logs request start with method, path, request_id
    - Logs request completion with status_code and duration_ms
    - Attaches request_id to response headers for tracing
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())[:8]

        # Bind request_id to structlog context for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        log = get_logger("http")
        log.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        )

        start_time = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Attach request_id to response headers so clients can trace
        response.headers["X-Request-ID"] = request_id

        log.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        return response
```

### `app/main.py`

Modify `D:\tis_project\app\main.py`:

Add these imports at the top:
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from app.core.logger import get_logger, StructuredLoggingMiddleware
```

Add Sentry init (before app creation):
```python
# ── Sentry initialization ────────────────────────────────────────────────────
sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN", ""),
    environment=os.environ.get("SENTRY_ENV", "development"),
    integrations=[
        FastApiIntegration(transaction_style="url"),
    ],
    # Ignore HTTP 400 — these are business logic errors, not bugs
    ignore_errors=[HTTPException],
    send_default_pii=False,
    traces_sample_rate=0.1,
)
```

Add logger middleware after CORS middleware:
```python
app.add_middleware(StructuredLoggingMiddleware)
```

Add logger to exception handler:
```python
log = get_logger("exception")
```

Full modified `app/main.py`:
```python
# app/main.py
import os
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.logger import get_logger, StructuredLoggingMiddleware

app = FastAPI(title="TIS API", version="1.0.0")

# ── Sentry initialization ────────────────────────────────────────────────────
sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN", ""),
    environment=os.environ.get("SENTRY_ENV", "development"),
    integrations=[
        FastApiIntegration(transaction_style="url"),
    ],
    ignore_errors=[HTTPException],
    send_default_pii=False,
    traces_sample_rate=0.1,
)

# CORS middleware - allow frontend on port 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Structured logging middleware
app.add_middleware(StructuredLoggingMiddleware)

@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    log = get_logger("exception")
    log.error("value_error", detail=str(exc))
    return JSONResponse(status_code=400, content={"detail": str(exc)})

from app.api.v1.endpoints import projects, documents, evaluations, rag, pricing, formal_review, review
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(evaluations.router)
app.include_router(rag.router)
app.include_router(pricing.router)
app.include_router(formal_review.router)
app.include_router(review.router)

@app.get("/health")
def health():
    return {"status": "ok"}
```

### `requirements.txt`

Add `sentry-sdk` to `D:\tis_project\requirements.txt`:

```
sentry-sdk>=2.0.0
```

### `.env.example`

Add Sentry variables to `D:\tis_project\.env.example`:

```
# Sentry (Error Tracking)
SENTRY_DSN=
SENTRY_ENV=production
```

### `frontend/package.json`

Add `@sentry/vue` to `D:\tis_project\frontend\package.json`:

```json
"dependencies": {
  ...
  "@sentry/vue": "^8.0.0"
}
```

### `frontend/src/main.ts`

Modify `D:\tis_project\frontend\src\main.ts`:

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import * as Sentry from '@sentry/vue'
import App from './App.vue'
import router from './router'
import './style.css'
import '@/api/mock'

// ── Sentry initialization ───────────────────────────────────────────────────
Sentry.init({
  dsn: import.meta.env.VITE_SENTRY_DSN || '',
  environment: import.meta.env.VITE_SENTRY_ENV || 'development',
  integrations: [
    Sentry.browserTracingIntegration(),
    Sentry.replayIntegration(),
  ],
  tracesSampleRate: 0.1,
  // Ignore HTTP 400s (business validation errors)
  ignoreErrors: [
    'Request failed with status 400',
    'HTTP 400',
  ],
  beforeSend(event) {
    // Only send uncaught 500-level errors
    const level = event.level
    if (level === 'warning' || level === 'info' || level === 'debug') {
      return null
    }
    return event
  },
})

const app = createApp(App)

// Register all Element Plus icons
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

// ── Sentry Vue plugin ────────────────────────────────
Sentry.setTag('app_name', 'tis-frontend')
app.config.errorHandler = (err, instance, info) => {
  Sentry.captureException(err, { extra: { info } })
}

app.mount('#app')
```

### Commit

```bash
git add app/core/logger.py app/main.py requirements.txt .env.example
git add frontend/package.json frontend/src/main.ts
git commit -m "feat(week8): add structured logging with structlog and Sentry exception monitoring"
```

---

## Task 3: CI/CD Workflow 本地验证 (可选)

**Files:**
- Create: `.github/workflows/production.yml` (already created in Task 1)

### 本地验证 CI/CD 配置

```bash
# Validate GitHub Actions YAML syntax
pip install check-jsonschema
check-jsonschema --builtin-schema vendor.github-workflows .github/workflows/production.yml

# Or use act to run workflows locally (if Docker available)
# act -s GITHUB_TOKEN=<mock> --workflows .github/workflows/production.yml
```

---

## Task 4: 回归测试与烟雾测试

**Files:**
- None (verification only)

### 验证所有测试依然全绿

```bash
cd /d/tis_project

# Backend regression
python -m pytest tests/week3/ tests/week4/ tests/week5/ -q --tb=short
# Expected: 105 + 53 + 58 = 216 passed (note: week6 tests may also exist)

# Frontend build
cd frontend && npm run build
# Expected: TypeScript check passes + Vite build succeeds

# Docker Compose config validation
docker compose config --quiet
# Expected: no errors
```

---

## Regression Gates

- All Week 3/4/5 backend tests must remain 100% green (isolated)
- `npm run build` in frontend must succeed with 0 TypeScript errors
- `docker compose config` must validate without errors
- `app/main.py` must import without Sentry errors when `SENTRY_DSN=""` (disabled)
- `frontend/src/main.ts` must run without errors when `VITE_SENTRY_DSN=""` (disabled)

---

## Summary

| Task | Component | Files | Type |
|------|-----------|-------|------|
| 1 | CI/CD Pipeline | `.github/workflows/production.yml`, `scripts/simulate_deploy.sh` | Create |
| 2 | Observability & Logging | `app/core/logger.py`, `app/main.py`, `requirements.txt`, `.env.example`, `frontend/package.json`, `frontend/src/main.ts` | Create + Modify |
| 3 | CI/CD Local Verification | — | Verification |
| 4 | Regression Tests | — | Verification |
| **Total** | | **~8 files** | |

**Sentry DSN Strategy:**
- Set `SENTRY_DSN=""` or leave empty → Sentry disabled (no-op, safe for local dev)
- Set real DSN in production environment variables → Sentry active
- Mock DSN for testing: `https://00000000000000000000000000000000@o000000.ingest.sentry.io/0000000`
