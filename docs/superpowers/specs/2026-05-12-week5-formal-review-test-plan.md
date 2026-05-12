# Week 5 形式审查测试计划

## 概述

**目标**：验证 TIS 系统 Week 5 形式审查功能，测试评审清单生成 → 确认项目 → 生成最终标书

**前置条件**：
- Week 1-2 E2E 测试已通过（Project 117 已创建）
- Week 3 RAG 生成测试已通过（3 个章节已生成）
- Week 4 定价博弈测试已通过（pricing_decision 已提交）

---

## 测试数据

### 项目信息
| 字段 | 值 |
|------|-----|
| 项目 ID | 117 |
| 项目状态 | awaiting_review |
| TechProposalTask | 需确认 status='confirmed' |
| PricingDecision | status='decided', boss_final_price=9,200,000 |

---

## 实现方案

### API 端点

| 步骤 | 方法 | 端点 | 功能 |
|------|------|------|------|
| 1 | GET | `/api/v1/projects/117/tech-proposal/current` | 查询 TechProposalTask |
| 2 | PUT | `/api/v1/tech-proposal-tasks/{id}/status` | 确认 tech proposal |
| 3 | POST | `/api/v1/projects/117/formal-review/initiate` | 生成评审清单 |
| 4 | GET | `/api/v1/projects/117/formal-review/status` | 查看评审状态 |
| 5 | POST | `/api/v1/formal-review-items/{id}/confirm` | 确认评审项 |
| 6 | POST | `/api/v1/projects/117/final-documents/generate` | 生成最终标书 |

---

## 执行步骤

### 步骤 1：查询 TechProposalTask

```bash
curl http://localhost:8000/api/v1/projects/117/tech-proposal/current
```

Expected: 返回 TechProposalTask，检查 status 字段

### 步骤 2：确认 TechProposalTask

如果 status != 'confirmed'：
```bash
curl -X PUT http://localhost:8000/api/v1/tech-proposal-tasks/{id}/status \
  -H "Content-Type: application/json" \
  -d '{"status": "confirmed"}'
```

### 步骤 3：发起形式审查

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/formal-review/initiate
```

Expected: HTTP 200, 返回 total_items 和 fatal_count

### 步骤 4：查看评审状态

```bash
curl http://localhost:8000/api/v1/projects/117/formal-review/status
```

Expected: 返回 FormalReviewStatusResponse

检查 fatal_pending > 0 是否阻止生成

### 步骤 5：确认评审项

如果 fatal_pending > 0：
```bash
# 先获取所有 fatal pending 项
curl "http://localhost:8000/api/v1/projects/117/formal-review/items?risk_level=fatal&status=pending"

# 逐个确认
curl -X POST http://localhost:8000/api/v1/formal-review-items/{id}/confirm
```

### 步骤 6：生成最终标书

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/final-documents/generate
```

Expected: HTTP 200, 返回 FinalDocGenerateResponse

---

## 验收标准

### 功能验收
- [ ] formal_review_items 表有 ≥1 条记录
- [ ] fatal_pending = 0（所有 fatal 项已确认）
- [ ] final_bid_documents 表有记录
- [ ] 生成 Word 文档成功

### 状态验收
- [ ] project 表 status = 'completed' 或类似终态

---

## 风险与备选

| 风险 | 缓解方案 |
|------|----------|
| TechProposalTask 不存在 | 检查数据库，确认 tech_proposal 数据 |
| fatal_pending > 0 阻止生成 | 确认所有 fatal 项后再生成 |
| 生成失败 | 检查 final_bid_documents 表是否有记录 |

---

## 创建时间
2026-05-12