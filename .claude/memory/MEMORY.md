# Project Memory

## 基础信息
- 项目名：TIS (高校食堂投标系统)
- 路径：D:\tis_project
- Git分支：master
- 主要语言：Python (FastAPI + SQLAlchemy) + Vue.js

## 技术栈
- 后端：FastAPI + PostgreSQL + pgvector
- 前端：Vue.js + Nginx
- 容器：Docker + Docker Compose
- LLM：DeepSeek v4 (deepseek-v4-flash / deepseek-v4-pro)

## 数据库
- Host: tis_db:5432
- DB: canteen_system
- 用户：postgres / Syk0215
- 容器内连接：postgresql://postgres:Syk0215@tis_db:5432/canteen_system

## 容器列表
- tis_backend (FastAPI) - 端口 8000 ✅
- tis_frontend (Vue.js) - 端口 3000
- tis_db (PostgreSQL + pgvector) - 内网 5432/对外 5433 ✅
- tis_ai_service - healthy ✅
- tis_redis, tis_minio, nginx

## 核心表结构
- knowledge_chunks: 知识块（content, content_vector, scoring_dimension_tags, win_signal）
- historical_tenders: 历史招标
- historical_bids: 历史投标
- internal_postmortems: 内部复盘
- projects: 项目表（活动数据）

## RAG配置
- 向量维度：BGE-small (512维)
- 检索方式：cosine distance (<=>)
- 评分维度：10维标签过滤
- 双轨RAG：positive/negative 双样本检索

## OutcomeBook修复（2026-04-28）
- **问题**：outcome_book.csv用tender文件hash，DB存bid文件，两者是不同文件SHA256
- **修复**：新增 `get_by_project_name()` 方法，通过project_name匹配outcome
- **位置**：`scripts/seeding/utils/outcome_book.py`
- **匹配逻辑**：4级fallback（exact → suffix-strip → substring-fuzzy → None）

## 快速命令
```bash
# win_signal验证
docker compose exec -T db psql -U postgres -d canteen_system -c "SELECT win_signal, COUNT(*) FROM knowledge_chunks GROUP BY win_signal;"

# 运行seeding pipeline
docker compose exec backend python3 -m scripts.seeding.run_import

# 验证outcome_book解析
docker compose exec backend python3 -c "from scripts.seeding.utils.outcome_book import OutcomeBook; from pathlib import Path; b = OutcomeBook.from_csv(Path('/data/historical_documents/outcome_book.csv')); print(f'rows_by_project: {len(b._rows_by_project)}')"
```
