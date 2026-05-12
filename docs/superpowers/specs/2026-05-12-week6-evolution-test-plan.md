# Week 6 Evolution 测试计划

## 概述

**目标**：验证 TIS 系统 Week 6 Evolution 功能，测试记录投标结果 → 分析 → 确认 → 知识进化完整流程

**前置条件**：
- Week 1-2 E2E 测试已通过（Project 117 已创建）
- Week 3 RAG 生成测试已通过（3 个章节已生成）
- Week 4 定价博弈测试已通过（pricing_decision 已提交）
- Week 5 形式审查测试已通过（final_bid_documents 已生成）

---

## 测试数据

### 项目信息
| 字段 | 值 |
|------|-----|
| 项目 ID | 117 |
| 项目状态 | awaiting_review |
| PricingDecision | boss_final_price=9,200,000, status='decided' |

---

## 实现方案

### API 端点

| 步骤 | 方法 | 端点 | 功能 |
|------|------|------|------|
| 1 | POST | `/api/v1/projects/117/outcomes/record` | 记录投标结果 |
| 2 | GET | `/api/v1/projects/117/review-analysis` | 查询评审分析 |
| 3 | POST | `/api/v1/projects/117/review-analysis/confirm` | 确认评审分析 |
| 4 | GET | `/api/v1/projects/117/rebid-alert` | 测试 rebid alert |
| 5 | GET | `/api/v1/knowledge-base/evolution-report` | 查询知识进化报告 |

---

## 执行步骤

### 步骤 1：记录投标结果 (lose)

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

Expected: HTTP 200, 返回 BidOutcomeResponse

### 步骤 2：查询评审分析

```bash
curl http://localhost:8000/api/v1/projects/117/review-analysis
```

Expected: HTTP 200, 返回 ReviewAnalysisResponse, outcome_status='lose'

### 步骤 3：确认评审分析

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/review-analysis/confirm \
  -H "Content-Type: application/json" \
  -d '{
    "confirmed_analysis": {"price_gap": 300000, "recommendation": "reduce_price"},
    "manual_notes": "报价偏高，需优化成本结构"
  }'
```

Expected: HTTP 200

### 步骤 4：测试 Rebid Alert

```bash
curl http://localhost:8000/api/v1/projects/117/rebid-alert
```

Expected: HTTP 200, 返回 RebidAlertResponse

### 步骤 5：生成知识进化报告

```bash
curl http://localhost:8000/api/v1/knowledge-base/evolution-report
```

Expected: HTTP 200, 返回 KnowledgeEvolutionReportResponse

### 步骤 6：测试 disqualified 结果（可选）

```bash
# 先清理旧数据
docker exec tis_db psql -U postgres -d canteen_system -c "DELETE FROM bid_outcomes WHERE project_id=117;"

# 记录 disqualified
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

---

## 验收标准

### 功能验收
- [ ] bid_outcomes 表有 ≥1 条记录
- [ ] knowledge_evolution_logs 表有记录
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
