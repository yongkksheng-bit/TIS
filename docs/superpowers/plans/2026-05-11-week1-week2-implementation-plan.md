# Week 1-2 端到端流程测试实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 解锁 TIS 系统完整流程测试，验证 projects 表从 0 条到有数据的流转

**Architecture:** 使用现有 6 个历史招标文件作为测试数据，通过 API 创建项目 → 上传招标文件 → 触发 RAG 初筛评估，验证完整数据流

**Tech Stack:** FastAPI (端口 8000), PostgreSQL/pgvector, Docker, curl/Playwright

---

## 概述

本计划执行 Week 1-2 端到端流程测试，使用现有 6 个历史招标文件解锁系统验证。

### 测试数据（已有）

| 文件名 | 大小 | 所属项目 |
|--------|------|----------|
| `2025_惠州交通大厦食堂管理和食材配送服务_招标文件.docx` | 83KB | 惠州交通局 |
| `2025_某部2026年副食品配送服务采购项目（第二次）_子包3_招标文件.docx` | 252KB | 某部子包3 |
| `2025_广东省粤北片区监狱（乐昌、韶关、武江、北江）2025-2026年度罪犯大宗生活物资（大米及食用油）采购项目_招标文件.docx` | 77KB | 粤北片区 |
| `2025_广东省肇庆片区（肇庆、四会、会城监狱）2025-2026年度服刑人员大宗生活物资（大米及食用油）采购项目_招标文件.docx` | 72KB | 肇庆片区 |
| `2025_监所羁押人员食堂食材配送服务采购项目_招标文件.docx` | 63KB | 监所羁押 |
| `2025_2026-2027年流浪乞讨人员伙房购买配送食材服务项目_采购包 1_招标文件.docx` | 101KB | 流浪乞讨 |

路径：`data/historical_documents/tenders/`

---

## 任务清单

### Task 1: 创建测试项目

**Files:**
- Modify: `docker-compose.yml` (验证容器状态)
- Test: API endpoint `POST /api/v1/projects`

- [ ] **Step 1: 验证 Docker 容器状态**

```bash
docker compose ps
```

Expected: tis_backend, tis_db, tis_ai_service, tis_minio, tis_redis, tis_frontend 全部 healthy

- [ ] **Step 2: 创建测试项目（惠州交通局）**

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "2025_惠州交通大厦食堂管理和食材配送服务",
    "agency_project_code": "HZJJ-2025001",
    "plan_code": "441301-2025-00001",
    "owner_unit": "惠州市交通运输局",
    "province": "广东",
    "region": "惠州"
  }'
```

Expected: JSON response with `id` field (e.g., `{"id": 1, ...}`)

- [ ] **Step 3: 验证 projects 表有数据**

```bash
docker exec tis_db psql -U canteen -d canteen_system -c "SELECT id, project_name, owner_unit FROM projects;"
```

Expected: ≥1 row returned

---

### Task 2: 上传招标文件

**Files:**
- Test: API endpoint `POST /api/v1/projects/{id}/upload-tender`

- [ ] **Step 1: 上传招标文件**

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/upload-tender \
  -F "file=@data/historical_documents/tenders/2025_惠州交通大厦食堂管理和食材配送服务_招标文件.docx"
```

Expected: JSON response with document metadata

- [ ] **Step 2: 验证 tender_documents 表有数据**

```bash
docker exec tis_db psql -U canteen -d canteen_system -c "SELECT id, project_id, file_name FROM tender_documents;"
```

Expected: ≥1 row returned

---

### Task 3: 触发初筛评估

**Files:**
- Test: API endpoint `POST /api/v1/projects/{id}/evaluations/generate`

- [ ] **Step 1: 触发 RAG 初筛评估**

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/evaluations/generate
```

Expected: HTTP 200 with evaluation result

- [ ] **Step 2: 检查评估结果**

```bash
docker exec tis_db psql -U canteen -d canteen_system -c "SELECT id, project_id, evaluation_status FROM evaluations LIMIT 5;"
```

Expected: ≥1 evaluation record

---

### Task 4: 验收确认

**Files:**
- Verify: Database state after all steps

- [ ] **Step 1: 确认 projects ≥1 条**

```bash
docker exec tis_db psql -U canteen -d canteen_system -c "SELECT COUNT(*) as project_count FROM projects;"
```

Expected: `project_count ≥ 1`

- [ ] **Step 2: 确认 tender_documents ≥1 条**

```bash
docker exec tis_db psql -U canteen -d canteen_system -c "SELECT COUNT(*) as doc_count FROM tender_documents;"
```

Expected: `doc_count ≥ 1`

- [ ] **Step 3: 确认 evaluations 表有记录**

```bash
docker exec tis_db psql -U canteen -d canteen_system -c "SELECT COUNT(*) as eval_count FROM evaluations;"
```

Expected: `eval_count ≥ 0` (评估可能需要更长时间)

---

### Task 5: (可选) Playwright E2E 测试脚本

**Files:**
- Create: `tests/e2e/test_week1_week2_flow.py`

- [ ] **Step 1: 创建 Playwright 测试脚本**

```python
import pytest
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8000"

def test_create_project():
    """测试创建项目"""
    response = requests.post(f"{BASE_URL}/api/v1/projects", json={
        "project_name": "测试项目",
        "agency_project_code": "TEST-001",
        "plan_code": "440000-2025-00001",
        "owner_unit": "测试单位",
        "province": "广东",
        "region": "广州"
    })
    assert response.status_code == 201
    assert "id" in response.json()

def test_upload_tender_document():
    """测试上传招标文件"""
    # 需要先创建项目获取 ID
    pass

def test_generate_evaluation():
    """测试触发初筛评估"""
    pass

def test_full_flow():
    """完整流程串联测试"""
    pass
```

- [ ] **Step 2: 运行 Playwright 测试**

```bash
cd tests/e2e
pytest test_week1_week2_flow.py -v
```

Expected: 3-4 tests passed

---

## 风险与备选

| 风险 | 缓解方案 |
|------|----------|
| API 端点不存在 | 先检查端点定义 |
| 文件上传失败 | 检查 MinIO 服务 |
| RAG 评估超时 | 检查 ai_service 健康状态 |

---

## 验收标准

### 方案 B（快速解锁）
- [x] projects 表有 ≥1 条记录
- [x] tender_documents 表有 ≥1 条记录
- [x] 初筛评估 API 返回 200

### 方案 C（E2E 测试）
- [ ] Playwright 测试脚本可运行
- [ ] 3 个测试用例全部通过
- [ ] 测试结果保存到测试报告

---

## 创建时间
2026-05-11

## 最后更新
2026-05-11 - 初始版本
