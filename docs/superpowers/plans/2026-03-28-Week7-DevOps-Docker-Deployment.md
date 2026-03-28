# Week 7: DevOps 与生产级容器化部署 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Containerize the TIS system with Docker Compose for production-ready deployment. Add a multi-stage Nginx frontend, harden the Python backend, and wire up the full 4-service stack (frontend + backend + PostgreSQL/pgvector + Redis).

**Architecture:**
- `docker-compose.yml` orchestrates 4 services: `frontend` (Nginx), `backend` (FastAPI/Uvicorn), `db` (PostgreSQL + pgvector), `redis` (cache)
- Backend uses `python:3.11-slim` with non-root user, healthcheck, and Alembic auto-migration on startup
- Frontend uses multi-stage build: Node.js 20 builder → Nginx:alpine for static asset serving with API proxy to backend
- Nginx forwards `/api/*` to `backend:8000` and serves Vue SPA static files for all other routes

**Tech Stack:** Docker, Docker Compose, Nginx, Python 3.11-slim, Node.js 20, pgvector/pg15, Redis 7

---

## File Structure

```
D:\tis_project\
  .env.example                    # MODIFY — production env vars template
  docker-compose.yml              # MODIFY — add frontend service, networks
  app/Dockerfile                 # MODIFY — harden for production
  docker/entrypoint.sh           # MODIFY — add seed data option
  frontend/Dockerfile            # CREATE — multi-stage Node→Nginx
  scripts/health_check.sh        # CREATE — container health verification
  docs/DEPLOY.md                # CREATE — production deployment guide
```

**Existing files already present (DO NOT RECREATE):**
- `docker-compose.yml` — skeleton with db, redis, minio, app (partial)
- `docker/entrypoint.sh` — alembic upgrade + uvicorn
- `app/Dockerfile` — base Python 3.11-slim (needs hardening)

---

## Dependency Chain

```
Task 1 (Environment整理) → Task 2 (Backend Dockerfile) → Task 3 (Frontend Dockerfile)
                                                                    ↓
Task 5 (Startup验证) ← Task 4 (Docker Compose编排)
```

---

## Task 1: Environment整理与环境变量规范化

**Files:**
- Create: `.env.example`
- Create: `scripts/health_check.sh`
- Modify: `start_all.bat` (add Docker awareness)
- Modify: `start_all.sh` (add Docker awareness)

### `.env.example`

Create `D:\tis_project\.env.example`:

```
# =======================
# TIS 系统环境变量模板
# =======================

# 数据库 (PostgreSQL + pgvector)
DATABASE_URL=postgresql://tis:tis@db:5432/tis
POSTGRES_DB=tis
POSTGRES_USER=tis
POSTGRES_PASSWORD=change_me_in_production

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO (对象存储)
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=change_me_in_production

# DeepSeek API (AI生成)
DEEPSEEK_API_KEY=your_api_key_here

# 前端 (Nginx uses these via build args)
VITE_API_BASE_URL=/api
NODE_ENV=production

# CORS (comma-separated allowed origins)
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

### `scripts/health_check.sh`

Create `D:\tis_project\scripts\health_check.sh`:

```bash
#!/bin/bash
# Health check script for TIS services
# Usage: ./scripts/health_check.sh [backend|frontend|all]

set -e

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
MAX_RETRIES=30
RETRY_INTERVAL=2

check_backend() {
    echo "Checking backend at $BACKEND_URL..."
    for i in $(seq 1 $MAX_RETRIES); do
        if curl -sf "$BACKEND_URL/health" > /dev/null 2>&1; then
            echo "✅ Backend is healthy"
            return 0
        fi
        echo "Attempt $i/$MAX_RETRIES: Backend not ready, waiting..."
        sleep $RETRY_INTERVAL
    done
    echo "❌ Backend health check failed"
    return 1
}

check_frontend() {
    echo "Checking frontend at $FRONTEND_URL..."
    for i in $(seq 1 $MAX_RETRIES); do
        if curl -sf "$FRONTEND_URL" > /dev/null 2>&1; then
            echo "✅ Frontend is healthy"
            return 0
        fi
        echo "Attempt $i/$MAX_RETRIES: Frontend not ready, waiting..."
        sleep $RETRY_INTERVAL
    done
    echo "❌ Frontend health check failed"
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
        check_backend
        check_frontend
        echo ""
        echo "🎉 All services are healthy!"
        ;;
    *)
        echo "Usage: $0 [backend|frontend|all]"
        exit 1
        ;;
esac
```

### Update `start_all.bat`

Modify `D:\tis_project\start_all.bat` to add Docker Compose option:

```batch
@echo off
title TIS - Tender Intelligence System

echo ============================================
echo  TIS 启动脚本
echo ============================================
echo.

echo 选择启动模式:
echo   [1] Docker Compose (推荐生产环境)
echo   [2] 本地开发模式 (前端 npm + 后端 uvicorn)
echo.
set /p choice="请选择 [1/2]: "

if "%choice%"=="1" goto docker_start
if "%choice%"=="2" goto dev_start
echo Invalid choice
exit /b 1

:docker_start
echo.
echo [1/2] 启动 Docker Compose (db + redis + backend + frontend)...
docker compose up -d
echo.
echo [2/2] 等待服务就绪...
call scripts\health_check.bat all
goto end

:dev_start
echo.
echo [1/3] Starting FastAPI Backend on port 8000...
start "TIS Backend" cmd /k "cd /d %~dp0 && python -m uvicorn app.main:app --reload --port 8000"
echo.
echo [2/3] Starting Vue Frontend on port 3000...
start "TIS Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
echo.
echo [3/3] Starting seed script (creates test data)...
python seed_db.py
goto end

:end
echo.
echo ============================================
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo   API Docs: http://localhost:8000/docs
echo ============================================
```

### Update `start_all.sh`

Similarly update `D:\tis_project\start_all.sh`:

```bash
#!/bin/bash
echo "TIS Startup Script"
echo "=================="
echo "Select mode:"
echo "  [1] Docker Compose (production)"
echo "  [2] Local dev (npm + uvicorn)"
read -p "Choice [1/2]: " choice

if [ "$choice" = "1" ]; then
    echo "Starting Docker Compose..."
    docker compose up -d
    echo "Waiting for services..."
    ./scripts/health_check.sh all
elif [ "$choice" = "2" ]; then
    echo "Starting local dev..."
    cd "$(dirname "$0")" && python -m uvicorn app.main:app --reload --port 8000 &
    cd frontend && npm run dev &
else
    echo "Invalid choice"
fi
```

### Commit

```bash
git add .env.example scripts/health_check.sh start_all.bat start_all.sh
git commit -m "feat(week7): add environment template and health check script"
```

---

## Task 2: Backend Dockerfile 生产级加固

**Files:**
- Modify: `app/Dockerfile` (hardened production image)
- Modify: `docker/entrypoint.sh` (add seed option)

### Hardened `app/Dockerfile`

Replace `D:\tis_project\app\Dockerfile` content:

```dockerfile
# =======================
# Stage 1: Builder
# =======================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
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

# Copy application
COPY --chown=appuser:appuser alembic/alembic.ini /app/alembic.ini
COPY --chown=appuser:appuser alembic/versions /app/alembic/versions
COPY --chown=appuser:appuser app/ /app/app/
COPY --chown=appuser:appuser requirements.txt /app/requirements.txt

# Set PATH for appuser
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Run migrations then start server
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

### Updated `docker/entrypoint.sh`

Modify `D:\tis_project\docker/entrypoint.sh`:

```bash
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
```

### Commit

```bash
git add app/Dockerfile docker/entrypoint.sh
git commit -m "feat(week7): harden backend Dockerfile with multi-stage build, non-root user, and healthcheck"
```

---

## Task 3: Frontend Multi-Stage Dockerfile

**Files:**
- Create: `frontend/Dockerfile` (Node 20 builder → Nginx:alpine)
- Modify: `frontend/vite.config.ts` (add base path for Docker deploy)

### `frontend/Dockerfile`

Create `D:\tis_project\frontend/Dockerfile`:

```dockerfile
# =======================
# Stage 1: Builder
# =======================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci --prefer-offline

# Copy source
COPY . .

# Build for production (VITE_USE_MOCK=false for Docker)
ARG VITE_USE_MOCK=false
ARG VITE_API_BASE_URL=/api
ENV VITE_USE_MOCK=$VITE_USE_MOCK
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# =======================
# Stage 2: Nginx Server
# =======================
FROM nginx:alpine AS runner

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx runs as nginx user by default (non-root)
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### `frontend/nginx.conf`

Create `D:\tis_project\frontend/nginx.conf`:

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 1000;

    # Vue SPA — serve index.html for all non-file routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy to FastAPI backend
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (for future use)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeout settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health endpoint
    location /health {
        access_log off;
        return 200 "OK\n";
        add_header Content-Type text/plain;
    }

    # Cache static assets aggressively
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### Update `frontend/vite.config.ts`

Modify `D:\tis_project\frontend/vite.config.ts` to support Docker base path:

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  // Docker production build uses relative base
  base: process.env.NODE_ENV === 'production' ? '/' : '/',
})
```

### Commit

```bash
git add frontend/Dockerfile frontend/nginx.conf frontend/vite.config.ts
git commit -m "feat(week7): add multi-stage frontend Dockerfile with Nginx API proxy"
```

---

## Task 4: Docker Compose 完整编排

**Files:**
- Modify: `docker-compose.yml` (add frontend service, networks, volumes)
- Modify: `.env.example` (add frontend vars)

### Complete `docker-compose.yml`

Replace `D:\tis_project\docker-compose.yml` with the following complete version:

```yaml
version: '3.8'

services:
  # ── PostgreSQL + pgvector ──────────────────────────────────────────
  db:
    image: pgvector/pgvector:pg15
    container_name: tis_db
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-tis}
      POSTGRES_USER: ${POSTGRES_USER:-tis}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-change_me_in_production}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-tis}"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s
    networks:
      - tis_net

  # ── Redis ────────────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    container_name: tis_redis
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - tis_net

  # ── MinIO (Object Storage) ─────────────────────────────────────────
  minio:
    image: minio/minio
    container_name: tis_minio
    ports:
      - "${MINIO_PORT:-9000}:9000"
      - "${MINIO_CONSOLE_PORT:-9001}:9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY:-change_me_in_production}
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3
    networks:
      - tis_net

  # ── FastAPI Backend ─────────────────────────────────────────────────
  backend:
    build:
      context: .
      dockerfile: app/Dockerfile
    container_name: tis_backend
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-tis}:${POSTGRES_PASSWORD:-change_me_in_production}@db:5432/${POSTGRES_DB:-tis}
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_SECRET_KEY: ${MINIO_SECRET_KEY:-change_me_in_production}
      DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY:-}
      CORS_ORIGINS: ${CORS_ORIGINS:-http://localhost:3000}
      INIT_DATA: ${INIT_DATA:-false}
    ports:
      - "${BACKEND_PORT:-8000}:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    networks:
      - tis_net

  # ── Vue Frontend (Nginx) ────────────────────────────────────────────
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        VITE_USE_MOCK: "false"
        VITE_API_BASE_URL: "/api"
    container_name: tis_frontend
    ports:
      - "${FRONTEND_PORT:-3000}:80"
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - tis_net

networks:
  tis_net:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

### Commit

```bash
git add docker-compose.yml
git commit -m "feat(week7): complete docker-compose with frontend Nginx service and full network topology"
```

---

## Task 5: 启动验证脚本与部署文档

**Files:**
- Create: `scripts/health_check.sh`
- Create: `docs/DEPLOY.md`
- Modify: `README.md` (add Docker Quick-Start section)

### `docs/DEPLOY.md`

Create `D:\tis_project\docs/DEPLOY.md`:

```markdown
# TIS 生产部署指南

## 环境要求

- Docker 24.0+
- Docker Compose v2.20+
- 最低配置：2 CPU / 4GB RAM / 20GB Disk

## 快速启动

### 1. 克隆并配置

```bash
git clone <repository-url>
cd tis_project

# 复制环境变量模板
cp .env.example .env

# 编辑 .env，修改以下必填项：
#   POSTGRES_PASSWORD=your_secure_password
#   MINIO_SECRET_KEY=your_secure_password
#   DEEPSEEK_API_KEY=your_deepseek_api_key
```

### 2. 一键启动

```bash
# 使用启动脚本
./start_all.sh
# 选择 [1] Docker Compose

# 或直接
docker compose up -d
./scripts/health_check.sh all
```

### 3. 验证服务

```bash
# 后端健康检查
curl http://localhost:8000/health

# 前端健康检查
curl http://localhost:3000/health

# API 文档
open http://localhost:8000/docs

# 前端界面
open http://localhost:3000
```

## 服务架构

```
                    ┌──────────────────────────────────────┐
Browser ──────►     │          Nginx (port 3000)            │
                    │   ┌────────────┐   ┌────────────────┐  │
                    │   │ Vue SPA    │   │ /api/* →       │  │
                    │   │ (static)   │   │ backend:8000   │  │
                    │   └────────────┘   └────────────────┘  │
                    └──────────────────────────────────────┘
                                         │
                    ┌────────────────────┴──────────────────┐
                    │         Docker Network (tis_net)        │
                    │                                           │
              ┌─────┴─────┐      ┌──────────────┐    ┌────────┐
              │ PostgreSQL │      │ FastAPI      │    │ Redis  │
              │ +pgvector │◄────►│ (Uvicorn)   │◄──►│ Cache  │
              │  port 5432│      │  port 8000  │    │ 6379   │
              └───────────┘      └──────────────┘    └────────┘
                                              │
                                        ┌─────┴──────┐
                                        │ MinIO      │
                                        │ :9000/:9001│
                                        └────────────┘
```

## 环境变量参考

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `POSTGRES_DB` | `tis` | 数据库名 |
| `POSTGRES_USER` | `tis` | 数据库用户 |
| `POSTGRES_PASSWORD` | `change_me` | **必须修改** 数据库密码 |
| `POSTGRES_PORT` | `5432` | PostgreSQL 端口 |
| `REDIS_PORT` | `6379` | Redis 端口 |
| `MINIO_PORT` | `9000` | MinIO API 端口 |
| `MINIO_CONSOLE_PORT` | `9001` | MinIO Console 端口 |
| `BACKEND_PORT` | `8000` | 后端 API 端口（映射到主机） |
| `FRONTEND_PORT` | `3000` | 前端 Nginx 端口（映射到主机） |
| `INIT_DATA` | `false` |设为 `true` 在首次启动时填充种子数据 |
| `DEEPSEEK_API_KEY` | _(空)_ | **必填** DeepSeek API Key |
| `CORS_ORIGINS` | `http://localhost:3000` | 允许的跨域来源（逗号分隔）|

## 数据库迁移

迁移在容器启动时自动执行（通过 `docker/entrypoint.sh`）。

手动执行迁移：
```bash
docker exec tis_backend alembic upgrade head
```

回滚迁移：
```bash
docker exec tis_backend alembic downgrade -1
```

## 首次使用：创建种子数据

```bash
# 方式一：设置环境变量自动 seed
INIT_DATA=true docker compose up -d

# 方式二：手动执行 seed 脚本
docker exec -it tis_backend python seed_db.py

# 登录信息
# 老板账号: boss_zhang
# 专员账号: specialist_li
# 财务账号: finance_wang
```

## 健康检查

```bash
# 检查所有服务
./scripts/health_check.sh all

# 仅检查后端
./scripts/health_check.sh backend

# 仅检查前端
./scripts/health_check.sh frontend
```

## 停止服务

```bash
docker compose down

# 删除数据卷（⚠️ 会清除所有数据）
docker compose down -v
```

## 生产环境注意事项

1. **修改所有密码** — 特别是 `POSTGRES_PASSWORD` 和 `MINIO_SECRET_KEY`
2. **配置备份** — 定期备份 `postgres_data` 和 `minio_data` Docker volumes
3. **HTTPS** — 生产环境应将 Nginx 前置于负载均衡器并配置 TLS
4. **资源限制** — 推荐为每个容器设置 memory/CPU limits
5. **日志收集** — 配置 Docker logging driver 收集容器日志

## 故障排查

```bash
# 查看后端日志
docker logs tis_backend -f

# 查看前端日志
docker logs tis_frontend -f

# 查看数据库日志
docker logs tis_db -f

# 进入后端容器调试
docker exec -it tis_backend /bin/bash

# 进入数据库
docker exec -it tis_db psql -U tis -d tis
```
```

### Commit

```bash
git add docs/DEPLOY.md scripts/health_check.sh
git commit -m "docs(week7): add deployment guide and health check verification script"
```

---

## Regression Gates

- All Week 3/4/5 backend tests must remain 100% green (isolated)
- All Week 6 frontend builds must remain 0 TypeScript errors
- `docker compose config` must validate without errors

---

## Summary

| Task | Component | New/Modified Files | Tests |
|------|-----------|-------------------|-------|
| 1 | Environment + Health Check | `.env.example`, `scripts/health_check.sh`, `start_all.{bat,sh}` | N/A |
| 2 | Backend Dockerfile | `app/Dockerfile`, `docker/entrypoint.sh` | N/A |
| 3 | Frontend Dockerfile | `frontend/Dockerfile`, `frontend/nginx.conf` | N/A |
| 4 | Docker Compose | `docker-compose.yml` | N/A |
| 5 | Verification + Docs | `docs/DEPLOY.md`, `scripts/health_check.sh` | N/A |
| **Total** | | **~8 files** | **N/A (infra)** |

**Regression:** Week 3 (105) + Week 4 (53) + Week 5 (58) + Week 6 backend (97) = **313 tests** must stay green.

**Mock/Real API Strategy:**
- `VITE_USE_MOCK=false` is baked into the frontend Docker build via `ARG`
- Frontend in Docker always talks to `http://backend:8000/api/`
- Local development continues to use `VITE_USE_MOCK=true` via `.env`
