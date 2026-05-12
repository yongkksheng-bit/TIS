# Week 5 形式审查测试实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 验证 Week 5 形式审查功能，测试评审清单生成 → 确认项目 → 生成最终标书

**Architecture:** 使用现有 Project 117，确认 tech_proposal → 生成评审清单 → 确认 fatal 项 → 生成最终标书

**Tech Stack:** FastAPI (端口 8000), PostgreSQL, Docker, curl

---

## 概述

本计划执行 Week 5 形式审查测试。

### 前置条件
- Project 117 存在
- PricingDecision 已提交 (status='decided')
- TechProposalTask 需确认 (status='confirmed')

### 测试数据

| 字段 | 值 |
|------|-----|
| 项目 ID | 117 |
| PricingDecision | boss_final_price=9,200,000, status='decided' |

---

## 任务清单

### Task 1: 查询 TechProposalTask

**Files:**
- Test: `GET /api/v1/projects/117/tech-proposal/current`

- [ ] **Step 1: 查询 TechProposalTask**

```bash
curl http://localhost:8000/api/v1/projects/117/tech-proposal/current
```

Expected: 返回 TechProposalTask，检查 status 字段

---

### Task 2: 确认 TechProposalTask

**Files:**
- Test: `PUT /api/v1/tech-proposal-tasks/{id}/status`

- [ ] **Step 1: 确认 TechProposalTask**

如果 status != 'confirmed'：
```bash
curl -X PUT http://localhost:8000/api/v1/tech-proposal-tasks/{id}/status \
  -H "Content-Type: application/json" \
  -d '{"status": "confirmed"}'
```

Expected: HTTP 200, status='confirmed'

---

### Task 3: 发起形式审查

**Files:**
- Test: `POST /api/v1/projects/117/formal-review/initiate`

- [ ] **Step 1: 发起形式审查**

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/formal-review/initiate
```

Expected: HTTP 200, 返回 total_items 和 fatal_count

---

### Task 4: 查看评审状态

**Files:**
- Test: `GET /api/v1/projects/117/formal-review/status`

- [ ] **Step 1: 查看评审状态**

```bash
curl http://localhost:8000/api/v1/projects/117/formal-review/status
```

Expected: 返回 FormalReviewStatusResponse

检查 fatal_pending 数量

---

### Task 5: 确认评审项

**Files:**
- Test: `POST /api/v1/formal-review-items/{id}/confirm`

- [ ] **Step 1: 获取所有 fatal pending 项**

```bash
curl "http://localhost:8000/api/v1/projects/117/formal-review/items?risk_level=fatal&status=pending"
```

- [ ] **Step 2: 逐个确认 fatal 项**

```bash
curl -X POST http://localhost:8000/api/v1/formal-review-items/{id}/confirm
```

Expected: 每个 fatal 项确认后 HTTP 200

---

### Task 6: 生成最终标书

**Files:**
- Test: `POST /api/v1/projects/117/final-documents/generate`

- [ ] **Step 1: 生成最终标书**

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/final-documents/generate
```

Expected: HTTP 200

---

### Task 7: 验收确认

**Files:**
- Verify: All formal review tables

- [ ] **Step 1: 验证 formal_review_items 表**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT COUNT(*) as count FROM formal_review_items WHERE project_id=117;"
```

Expected: `count ≥ 1`

- [ ] **Step 2: 验证 final_bid_documents 表**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT COUNT(*) as count FROM final_bid_documents WHERE project_id=117;"
```

Expected: `count ≥ 1`

- [ ] **Step 3: 验证项目状态**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT id, status FROM projects WHERE id=117;"
```

Expected: status 已更新

---

## 验收标准

### 功能验收
- [x] formal_review_items 表有 ≥1 条记录
- [x] fatal_pending = 0
- [x] final_bid_documents 表有记录
- [x] 生成 Word 文档成功

### 状态验收
- [x] project 表 status 已更新

---

## 风险与备选

| 风险 | 缓解方案 |
|------|----------|
| TechProposalTask 不存在 | 检查数据库确认数据 |
| fatal_pending > 0 阻止生成 | 确认所有 fatal 项后再生成 |
| 生成失败 | 检查 final_bid_documents 表 |

---

## 创建时间
2026-05-12

## 最后更新
2026-05-12 - 初始版本