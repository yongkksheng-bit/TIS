# TIS - 高校食堂投标系统

[![CI](https://github.com/yongkksheng-bit/TIS/actions/workflows/ci.yml/badge.svg)](https://github.com/yongkksheng-bit/TIS/actions/workflows/ci.yml)

RAG-based tender intelligence system for university canteen procurement.

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy + PostgreSQL/pgvector
- **Frontend**: Vue.js
- **RAG**: Historical tender/bid knowledge management with 10-dimensional scoring
- **LLM**: DeepSeek v4

## Development

```bash
# Start services
docker compose up -d

# Run tests
pytest tests/

# Run smoke tests
bash scripts/daily_smoke_test.sh
```