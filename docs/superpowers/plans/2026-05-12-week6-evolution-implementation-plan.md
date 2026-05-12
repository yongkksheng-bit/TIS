# Week 6 Evolution 测试实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 验证 Week 6 Evolution 功能，测试记录投标结果 → 分析 → 确认 → 知识进化完整流程

**Architecture:** 使用现有 Project 117，记录 lose/disqualified 结果 → 验证 bid_outcomes/winning_dna/disqualification_traps/knowledge_evolution_logs 表更新

**Tech Stack:** FastAPI (端口 8000), PostgreSQL, Docker, curl

---

## 概述

本计划执行 Week 6 Evolution 测试，使用现有项目 Project 117。

### 前置条件
- Project 117 存在
- Week 5 已完成（formal_review_items, final_bid_documents 已生成）
- PricingDecision 已提交 (status='decided', boss_final_price=9,200,000)

### 测试数据

| 字段 | 值 |
|------|-----|
| 项目 ID | 117 |
| outcome_status | lose |
| final_bid_price | 9,200,000 |
| winning_price | 9,500,000 |
| disqualification_reason | 报价偏高 |

---

## 任务清单

### Task 1: 记录投标结果 (lose)

**Files:**
- Test: `POST /api/v1/projects/117/outcomes/record`

- [ ] **Step 1: 记录 lose 结果**

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/outcomes/record \
  -H "Content-Type: application/json" \
  -d '{
    "outcome_status": "lose",
    "outcome_date": "2026-05-12",
    "final_bid_price": 9200000,
    "winning_price": 9500000,
    "our_price_rank": 2,
    "extract_dna": false,
    "update_traps": false
  }'
```

Expected: HTTP 200, 返回 BidOutcomeResponse, outcome_status='lose'

- [ ] **Step 2: 验证 bid_outcomes 表**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT id, project_id, outcome_status, final_bid_price, winning_price FROM bid_outcomes WHERE project_id=117 ORDER BY id;"
```

Expected: 1 row, outcome_status='lose', final_bid_price=9200000, winning_price=9500000

- [ ] **Step 3: 验证 knowledge_evolution_logs 表**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT COUNT(*) as count FROM knowledge_evolution_logs WHERE project_id=117;"
```

Expected: count >= 0 (Project 117 自身无 chunks，logs 可能为 0)

---

### Task 2: 查询评审分析

**Files:**
- Test: `GET /api/v1/projects/117/review-analysis`

- [ ] **Step 1: 查询评审分析**

```bash
curl http://localhost:8000/api/v1/projects/117/review-analysis
```

Expected: HTTP 200, 返回 ReviewAnalysisResponse, outcome_status='lose'

---

### Task 3: 确认评审分析

**Files:**
- Test: `POST /api/v1/projects/117/review-analysis/confirm`

- [ ] **Step 1: 确认评审分析**

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/review-analysis/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "confirmed_analysis": {"price_gap": 300000, "recommendation": "reduce_price"},
    "manual_notes": "报价偏高，需优化成本结构"
  }'
```

Expected: HTTP 200

- [ ] **Step 2: 验证 bid_outcomes reviewed 字段**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT id, reviewed_by, reviewed_at, review_notes FROM bid_outcomes WHERE project_id=117 ORDER BY id;"
```

Expected: reviewed_by 和 reviewed_at 有值

---

### Task 4: 测试 Rebid Alert

**Files:**
- Test: `GET /api/v1/projects/117/rebid-alert`

- [ ] **Step 1: 查询 rebid alert**

```bash
curl http://localhost:8000/api/v1/projects/117/rebid-alert
```

Expected: HTTP 200, 返回 RebidAlertResponse

---

### Task 5: 生成知识进化报告

**Files:**
- Test: `GET /api/v1/knowledge-base/evolution-report`

- [ ] **Step 1: 查询知识进化报告**

```bash
curl http://localhost:8000/api/v1/knowledge-base/evolution-report
```

Expected: HTTP 200, 返回 KnowledgeEvolutionReportResponse

- [ ] **Step 2: 验证报告内容**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT total_chunks, deprecated_this_month, weighted_by_wins, new_traps_added FROM knowledge_evolution_logs LIMIT 1;"
```

---

### Task 6: 测试 disqualified 结果（可选）

**Files:**
- Test: `POST /api/v1/projects/117/outcomes/record`

- [ ] **Step 1: 清理旧数据（可选）**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "DELETE FROM bid_outcomes WHERE project_id=117;"
```

- [ ] **Step 2: 记录 disqualified 结果**

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/outcomes/record \
  -H "Content-Type: application/json" \
  -d '{
    "outcome_status": "disqualified",
    "outcome_date": "2026-05-12",
    "final_bid_price": 9200000,
    "disqualification_reason": "资质文件不完整",
    "disqualification_type": "fatal_qualification",
    "extract_dna": false,
    "update_traps": true
  }'
```

Expected: HTTP 200, outcome_status='disqualified'

- [ ] **Step 3: 验证 disqualification_traps 表**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT COUNT(*) as count FROM disqualification_traps;"
```

Expected: count >= 1（如果 trap 不存在则新建）

---

### Task 7: 验收确认

**Files:**
- Verify: All Week 6 tables

- [ ] **Step 1: 验证 bid_outcomes 表**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT COUNT(*) as count FROM bid_outcomes WHERE project_id=117;"
```

Expected: count >= 1

- [ ] **Step 2: 验证 knowledge_evolution_logs 表**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT COUNT(*) as count FROM knowledge_evolution_logs;"
```

Expected: count >= 0

- [ ] **Step 3: 验证 disqualification_traps 表**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT COUNT(*) as count FROM disqualification_traps;"
```

Expected: count >= 0

- [ ] **Step 4: 验证所有表计数**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT 'bid_outcomes' as tbl, COUNT(*) as cnt FROM bid_outcomes WHERE project_id=117 UNION ALL SELECT 'winning_dna', COUNT(*) FROM winning_dna WHERE project_id=117 UNION ALL SELECT 'disqualification_traps', COUNT(*) FROM disqualification_traps UNION ALL SELECT 'knowledge_evolution_logs', COUNT(*) FROM knowledge_evolution_logs WHERE project_id=117;"
```

---

## 验收标准

### 功能验收
- [ ] bid_outcomes 表有 ≥1 条记录
- [ ] knowledge_evolution_logs 表有记录（lose 场景）
- [ ] disqualified 场景正确创建 disqualification_traps
- [ ] review-analysis 返回正确的分析结果
- [ ] rebid-alert 返回 RebidAlertResponse
- [ ] evolution-report 返回 KnowledgeEvolutionReportResponse

### 状态验收
- [ ] bid_outcomes.reviewed_by 和 reviewed_at 在确认后有值

---

## 风险与备选

| 风险 | 缓解方案 |
|------|----------|
| Project 117 无 confirmed tech_proposal | lose/disqualified 不依赖 tech_proposal |
| winning_dna 无数据（无 tech_proposal） | extract_dna=false，跳过 DNA 提取 |
| disqualified_traps 可能已存在 | 使用 ON CONFLICT DO UPDATE |
| knowledge_evolution_logs 无数据 | Project 117 自身无 chunks，可接受 |

---

## 创建时间
2026-05-12

## 最后更新
2026-05-12 - 初始版本
