# Week 3 RAG 生成测试实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 验证 Week 3 RAG 生成技术方案功能，生成 3 个章节并验证双轨 RAG 检索

**Architecture:** 使用现有 Project 117，通过 `POST /api/v1/projects/117/generate-section` 生成多章节，验证 `project_sections` 表存储

**Tech Stack:** FastAPI (端口 8000), PostgreSQL/pgvector, Docker, curl

---

## 概述

本计划执行 Week 3 RAG 生成测试，使用现有项目 Project 117 (id=117) 生成 3 个技术方案章节，并验证双轨 RAG 功能。

### 前置条件
- Project 117 已存在（Week 1-2 测试创建）
- 双轨 RAG 数据已就绪：positive=6140, negative=7585

### 测试数据

| 字段 | 值 |
|------|-----|
| 项目 ID | 117 |
| 项目名称 | HZ_2025_Canteen_Test |

### 测试章节

| 序号 | 章节名称 | scoring_dimension_tags |
|------|----------|------------------------|
| 1 | 第一章：冷链配送方案 | 配送能力 |
| 2 | 第二章：食材溯源方案 | 食材溯源 |
| 3 | 第三章：服务保障方案 | 服务方案 |

---

## 任务清单

### Task 1: 生成第一章（冷链配送方案）

**Files:**
- Test: `POST /api/v1/projects/117/generate-section`

- [ ] **Step 1: 触发第一章生成**

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/generate-section \
  -H "Content-Type: application/json" \
  -d '{
    "section_name": "第一章：冷链配送方案",
    "generation_mode": "auto",
    "top_k": 5,
    "scoring_dimension_tags": ["配送能力"],
    "region_tags": ["广东省"],
    "use_dual_track_rag": true
  }'
```

Expected: HTTP 200, `"section_name": "第一章：冷链配送方案"`, content non-empty, source_chunk_count > 0

- [ ] **Step 2: 验证响应结构**

检查返回 JSON 包含：
- `code: 0`
- `data.project_id: 117`
- `data.section_name: "第一章：冷链配送方案"`
- `data.content` 非空
- `data.token_usage` 有值
- `data.source_chunk_count > 0`

---

### Task 2: 生成第二章（食材溯源方案）

**Files:**
- Test: `POST /api/v1/projects/117/generate-section`

- [ ] **Step 1: 触发第二章生成**

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/generate-section \
  -H "Content-Type: application/json" \
  -d '{
    "section_name": "第二章：食材溯源方案",
    "generation_mode": "auto",
    "top_k": 5,
    "scoring_dimension_tags": ["食材溯源"],
    "region_tags": ["广东省"],
    "use_dual_track_rag": true
  }'
```

Expected: HTTP 200, content non-empty

---

### Task 3: 生成第三章（服务保障方案）

**Files:**
- Test: `POST /api/v1/projects/117/generate-section`

- [ ] **Step 1: 触发第三章生成**

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/generate-section \
  -H "Content-Type: application/json" \
  -d '{
    "section_name": "第三章：服务保障方案",
    "generation_mode": "auto",
    "top_k": 5,
    "scoring_dimension_tags": ["服务方案"],
    "region_tags": ["广东省"],
    "use_dual_track_rag": true
  }'
```

Expected: HTTP 200, content non-empty

---

### Task 4: 验收确认

**Files:**
- Test: `GET /api/v1/projects/117/sections`

- [ ] **Step 1: 查询章节列表 API**

```bash
curl http://localhost:8000/api/v1/projects/117/sections
```

Expected: 返回 3 个章节，sections 数组长度 = 3

- [ ] **Step 2: 验证数据库 project_sections 表**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT id, project_id, section_name, LENGTH(content) as content_len FROM project_sections WHERE project_id=117 ORDER BY id;"
```

Expected: ≥3 rows, 每个 content_len > 0

- [ ] **Step 3: 验证章节内容**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT section_name, SUBSTRING(content, 1, 50) as preview FROM project_sections WHERE project_id=117;"
```

Expected: 每个章节都有 content preview

---

### Task 5: (可选) 双轨 RAG 验证

**Files:**
- Verify: RAG retrieval logs

- [ ] **Step 1: 验证 retrieve_positive_samples 和 retrieve_negative_samples**

```bash
docker exec tis_backend python3 -c "
from app.core.week3_rag.retriever import DocumentRetriever
from app.core.week3_rag.embedder import create_embedder
from app.models import Base
from app.dependencies import SessionLocal

db = SessionLocal()
embedder = create_embedder()
retriever = DocumentRetriever(db, embedder)

# 测试 retrieval
positive = retriever.retrieve_positive_samples(query='冷链配送', top_k=3)
negative = retriever.retrieve_negative_samples(query='冷链配送', top_k=3)

print(f'Positive samples: {len(positive)}')
print(f'Negative samples: {len(negative)}')
db.close()
"
```

Expected: positive > 0, negative > 0

---

## 验收标准

### 功能验收
- [x] 生成 3 个章节全部返回 HTTP 200
- [x] 每个章节 content 非空
- [x] `use_dual_track_rag=True` 启用（positive/negative 样本检索）
- [x] 章节存储到 project_sections 表

### 数据验收
- [x] project_sections 表有 ≥3 条记录
- [x] 每个 section_name 唯一

### 性能验收
- [ ] 单章节生成时间 < 60s

---

## 风险与备选

| 风险 | 缓解方案 |
|------|----------|
| LLM 超时（>120s）| 检查 ai_service 健康状态 `docker compose ps` |
| RAG 返回 0 chunks | 验证 win_signal 分布 `SELECT COUNT(*) WHERE win_signal='positive'` |
| 内容为空 | 检查 use_dual_track_rag 参数是否正确传递 |
| 存储失败 | 检查 project_sections 表是否存在 |

---

## 创建时间
2026-05-11

## 最后更新
2026-05-11 - 初始版本