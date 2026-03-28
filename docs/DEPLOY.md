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
| `INIT_DATA` | `false` | 设为 `true` 在首次启动时填充种子数据 |
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