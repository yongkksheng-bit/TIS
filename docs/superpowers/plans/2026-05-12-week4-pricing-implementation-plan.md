# Week 4 定价博弈测试实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 验证 Week 4 定价博弈功能，测试成本估算 → 博弈模型 → 定价决策完整流程

**Architecture:** 使用现有 Project 117，设置预算 → 创建成本估算 → 确认 → 生成A/B/C方案 → 提交决策

**Tech Stack:** FastAPI (端口 8000), PostgreSQL, Docker, curl

---

## 概述

本计划执行 Week 4 定价博弈测试，使用现有项目 Project 117。

### 前置条件
- Project 117 存在（Week 1-2/3 测试创建）

### 测试数据

| 字段 | 值 |
|------|-----|
| 项目 ID | 117 |
| 预算金额 | 9,000,000 |

### 成本估算参数

| 成本项 | 金额 |
|--------|------|
| food_cost | 6,300,000 |
| logistics_cost | 1,350,000 |
| labor_cost | 900,000 |
| management_cost | 450,000 |
| **总计** | **9,000,000** |

---

## 任务清单

### Task 1: 设置项目预算

**Files:**
- Modify: `projects` table

- [ ] **Step 1: 设置 Project 117 的 budget_amount**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "UPDATE projects SET budget_amount = 9000000 WHERE id = 117 RETURNING id, project_name, budget_amount;"
```

Expected: `budget_amount = 9000000`

---

### Task 2: 创建成本估算

**Files:**
- Test: `POST /api/v1/projects/117/cost-estimates`

- [ ] **Step 1: 创建成本估算**

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

Expected: HTTP 200, 返回 cost_estimate id (记下这个 id 用于下一步)

- [ ] **Step 2: 验证 cost_estimates 表**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT id, project_id, total_cost, is_confirmed FROM cost_estimates WHERE project_id=117;"
```

Expected: ≥1 row

---

### Task 3: 确认成本估算

**Files:**
- Test: `POST /api/v1/cost-estimates/{id}/confirm`

- [ ] **Step 1: 确认成本估算**

使用 Task 2 返回的 id：

```bash
curl -X POST http://localhost:8000/api/v1/cost-estimates/{id}/confirm
```

Expected: HTTP 200, `is_confirmed: true`

- [ ] **Step 2: 验证确认状态**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT id, project_id, is_confirmed FROM cost_estimates WHERE project_id=117 AND is_confirmed=true;"
```

Expected: ≥1 row with `is_confirmed = true`

---

### Task 4: 生成定价方案

**Files:**
- Test: `POST /api/v1/projects/117/pricing-calculations`

- [ ] **Step 1: 生成 A/B/C 定价方案**

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/pricing-calculations
```

Expected: HTTP 200, 返回 3 种方案（aggressive, balanced, conservative）

每种方案包含：
- `scenario`: 方案名称
- `price`: 价格
- `label`: 标签
- `win_prob`: 胜率
- `profit`: 利润
- `expected_value`: 期望值
- `risk_level`: 风险等级
- `is_recommended`: 是否推荐

---

### Task 5: 提交定价决策

**Files:**
- Test: `POST /api/v1/projects/117/pricing-decisions`

- [ ] **Step 1: 提交最终定价决策**

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

- [ ] **Step 2: 验证 pricing_decisions 表**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT id, project_id, boss_final_price, boss_decision_reason FROM pricing_decisions WHERE project_id=117;"
```

Expected: ≥1 row

---

### Task 6: 验收确认

**Files:**
- Verify: All pricing tables

- [ ] **Step 1: 验证 cost_estimates 表**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT COUNT(*) as count FROM cost_estimates WHERE project_id=117;"
```

Expected: `count ≥ 1`

- [ ] **Step 2: 验证 pricing_decisions 表**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT COUNT(*) as count FROM pricing_decisions WHERE project_id=117;"
```

Expected: `count ≥ 1`

- [ ] **Step 3: 验证所有数据关联**

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT p.id, p.budget_amount, c.total_cost, c.is_confirmed, pd.boss_final_price FROM projects p LEFT JOIN cost_estimates c ON p.id=c.project_id LEFT JOIN pricing_decisions pd ON p.id=pd.project_id WHERE p.id=117;"
```

Expected: budget_amount=9000000, total_cost=9000000, is_confirmed=true, boss_final_price=8800000

---

## 验收标准

### 功能验收
- [x] cost_estimates 表有 ≥1 条记录
- [x] cost_estimates.is_confirmed = true 存在
- [x] pricing_calculations 返回 3 种方案
- [x] pricing_decisions 表有 ≥1 条记录

### 业务验收
- [x] A/B/C 三种方案价格合理
- [x] recommended 方案被标记

---

## 风险与备选

| 风险 | 缓解方案 |
|------|----------|
| budget_amount 为 NULL | Task 1 已设置 |
| cost_estimate 未确认 | Task 3 确认后再继续 |
| 定价决策失败 | boss_final_price > 0 |

---

## 创建时间
2026-05-12

## 最后更新
2026-05-12 - 初始版本