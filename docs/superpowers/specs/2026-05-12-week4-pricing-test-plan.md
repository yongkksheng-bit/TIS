# Week 4 定价博弈测试计划

## 概述

**目标**：验证 TIS 系统 Week 4 定价博弈功能，测试成本估算 → 博弈模型 → 定价决策完整流程

**前置条件**：
- Week 1-2 E2E 测试已通过（Project 117 已创建）
- Week 3 RAG 生成测试已通过（3 个章节已生成）

---

## 测试数据

### 项目信息
| 字段 | 值 |
|------|-----|
| 项目 ID | 117 |
| 项目名称 | HZ_2025_Canteen_Test |
| 预算金额 | 9,000,000（来自 historical tender 77）|

### 成本估算参数（基于历史数据比例）

| 成本项 | 比例 | 金额 |
|--------|------|------|
| 食材成本 (food_cost) | 70% | 6,300,000 |
| 物流成本 (logistics_cost) | 15% | 1,350,000 |
| 人工成本 (labor_cost) | 10% | 900,000 |
| 管理成本 (management_cost) | 5% | 450,000 |
| **总计** | 100% | **9,000,000** |

---

## 实现方案

### API 端点

| 步骤 | 方法 | 端点 | 功能 |
|------|------|------|------|
| 1 | UPDATE | projects 表 | 设置 budget_amount = 9,000,000 |
| 2 | POST | `/api/v1/projects/117/cost-estimates` | 创建成本估算 |
| 3 | POST | `/api/v1/cost-estimates/{id}/confirm` | 确认成本估算 |
| 4 | POST | `/api/v1/projects/117/pricing-calculations` | 生成 A/B/C 定价方案 |
| 5 | POST | `/api/v1/projects/117/pricing-decisions` | 提交最终定价决策 |

---

## 执行步骤

### 步骤 1：设置项目预算

```sql
UPDATE projects SET budget_amount = 9000000 WHERE id = 117;
```

### 步骤 2：创建成本估算

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/cost-estimates \
  -H "Content-Type: application/json" \
  -d '{
    "food_cost": 6300000,
    "logistics_cost": 1350000,
    "labor_cost": 900000,
    "management_cost": 450000,
    "other_cost": 0,
    "estimate_reason": "基于惠州交通大厦历史项目成本比例测算"
  }'
```

Expected: HTTP 200, 返回 cost_estimate id

### 步骤 3：确认成本估算

```bash
curl -X POST http://localhost:8000/api/v1/cost-estimates/{id}/confirm
```

Expected: HTTP 200, `is_confirmed: true`

### 步骤 4：生成定价方案

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/pricing-calculations
```

Expected: HTTP 200, 返回 A/B/C 三种定价方案：
- aggressive（激进）
- balanced（平衡）
- conservative（保守）

每种方案包含：price, win_prob, profit, expected_value, risk_level

### 步骤 5：提交定价决策

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/pricing-decisions \
  -H "Content-Type: application/json" \
  -d '{
    "boss_final_price": 8800000,
    "boss_decision_reason": "基于市场博弈模型选择平衡定价策略",
    "deviation_reason_category": "profit_reserve"
  }'
```

Expected: HTTP 200

---

## 验收标准

### 功能验收
- [ ] `cost_estimates` 表有 ≥1 条记录
- [ ] `is_confirmed=True` 的估算存在
- [ ] `/pricing-calculations` 返回 3 种方案（A/B/C）
- [ ] 每种方案的 price, win_prob, profit, expected_value 非空
- [ ] `pricing_decisions` 表有 ≥1 条记录

### 业务验收
- [ ] A/B/C 三种方案价格递增或递减
- [ ] recommended 方案被标记

---

## 风险与备选

| 风险 | 缓解方案 |
|------|----------|
| budget_amount 为 NULL | 先 UPDATE 设置预算 |
| cost_estimate 未确认 | 确认后再调用 pricing-calculations |
| 定价决策失败 | 检查 boss_final_price > 0 |

---

## 创建时间
2026-05-12