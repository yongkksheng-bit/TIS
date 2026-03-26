# Week 4 Implementation Plan: 智能定价决策系统 (IPDS)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现从成本录入 → 博弈定价计算 → 定价决策确认 → 版本追溯的完整闭环，支持三角色录入、系统博弈分析、三级价格管控、拦截规则强制校验。

**Architecture:**
- 定价层作为 Week 3→Week 5 的桥梁：技术标确认完成后进入 `AWAITING_PRICING` 状态，定价决策确认后推进至 `AWAITING_REVIEW`
- 三张新表：`cost_estimates`（版本化成本）、`pricing_decisions`（三级价格决策）、`price_history`（历史数据积累）
- 博弈模型支持冷启动：历史数据 < 5 条时降级为规则启发式算法
- 所有金额字段使用 `Decimal` 防止浮点精度丢失

**Tech Stack:** Python `decimal.Decimal`, SQLAlchemy, FastAPI, Alembic — 无需外部文档库（Word/PDF 生成属于 Week 5）

---

## File Structure

```
app/models/
  pricing.py               # CostEstimate, PricingDecision, PriceHistory (NEW)

app/core/week4_pricing/
  cost_engine.py           # CostEstimationEngine (历史推算 + 比例拆解)
  game_theory.py           # PricingGameTheoryModel (冷启动概率 + 场景生成)
  intercept_rules.py       # 定价拦截规则 (倒挂/亏损/超限/差异过大)

app/schemas/week4.py       # Pydantic schemas (CostEstimate, PricingDecision, Scenario)

app/api/v1/endpoints/
  pricing.py               # 定价层 API 路由 (NEW)

alembic/versions/
  w004_add_pricing_tables.py  # Migration: cost_estimates, pricing_decisions, price_history

tests/week3/              (Week 3 tests remain unchanged)
tests/week4/
  test_week4_migrations.py # Migration + FK + CASCADE tests
  test_pricing_models.py   # SQLAlchemy model tests
  test_cost_engine.py      # 成本估算引擎测试
  test_game_theory.py      # 博弈模型测试
  test_intercept_rules.py  # 拦截规则测试
  test_week4_schemas.py    # Pydantic schema validation tests
  test_pricing_api.py      # API 端点测试
```

---

## Task 1: Alembic Migration + SQLAlchemy Models (Week 4 Pricing Tables)

**Files:**
- Create: `alembic/versions/w004_add_pricing_tables.py`
- Create: `app/models/pricing.py`
- Create: `tests/week4/test_week4_migrations.py`
- Create: `tests/week4/test_pricing_models.py`

### Sub-Steps

- [ ] **Step 1: Write failing migration + model tests**

```python
# tests/week4/test_week4_migrations.py
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

@pytest.fixture
def db_conn():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(100) NOT NULL UNIQUE
            )
        """))
        conn.execute(text("""
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name VARCHAR(255) NOT NULL,
                project_type VARCHAR(50),
                owner_unit VARCHAR(255),
                owner_type VARCHAR(50) DEFAULT 'enterprise',
                region VARCHAR(100),
                budget_amount NUMERIC(15, 2),
                bid_open_date TIMESTAMP,
                status VARCHAR(50) NOT NULL DEFAULT 'uploaded',
                relationship_flag INTEGER NOT NULL DEFAULT 0,
                generation_mode VARCHAR(20),
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
    return engine.connect()

def test_cost_estimates_table_exists(db_conn):
    from alembic import command
    from alembic.config import Config
    # Run migration on in-memory DB
    ...
    result = db_conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='cost_estimates'"
    )).fetchone()
    assert result is not None

def test_pricing_decisions_table_exists(db_conn): ...
def test_price_history_table_exists(db_conn): ...
def test_cost_estimates_columns(db_conn):
    columns = {r[1] for r in db_conn.execute(text("PRAGMA table_info(cost_estimates)"))}
    assert 'food_cost' in columns
    assert 'logistics_cost' in columns
    assert 'labor_cost' in columns
    assert 'management_cost' in columns
    assert 'total_cost' in columns
    assert 'version_number' in columns
def test_pricing_decisions_has_game_theory_jsonb(db_conn):
    columns = {r[1] for r in db_conn.execute(text("PRAGMA table_info(pricing_decisions)"))}
    assert 'game_theory_analysis' in columns
    assert 'boss_final_price' in columns
    assert 'system_suggested_optimal' in columns
def test_price_history_columns(db_conn): ...
def test_cost_estimates_project_fk(db_conn):
    fks = db_conn.execute(text("PRAGMA foreign_key_list(cost_estimates)")).fetchall()
    assert any(fk[2] == 'projects' for fk in fks)
def test_cascade_delete_project_removes_cost_estimates(db_conn):
    """Deleting project removes associated cost_estimates."""
    # Insert project, cost_estimate, delete project, verify cost_estimate gone
    ...
def test_migration_reproducible(db_conn):
    """Migration can run twice (idempotent up/down)."""
    ...
```

```python
# tests/week4/test_pricing_models.py
from decimal import Decimal
from app.models.pricing import CostEstimate, PricingDecision, PriceHistory

def test_cost_estimate_total_cost_is_sum(db_session):
    """total_cost = food + logistics + labor + management + other."""
    est = CostEstimate(
        project_id=1, version_number=1,
        food_cost=Decimal('100000'), logistics_cost=Decimal('20000'),
        labor_cost=Decimal('50000'), management_cost=Decimal('20000'),
        other_cost=Decimal('0'),
        estimated_by=1, estimate_reason="Test",
    )
    db_session.add(est); db_session.commit()
    assert est.total_cost == Decimal('190000')

def test_cost_estimate_version_isolation_per_project(db_session):
    """Same project: each new estimate gets incremented version_number."""
    # est1: v1, est2: v2
    ...

def test_pricing_decision_system_suggested_order(db_session):
    """system_suggested_low < system_suggested_optimal < system_suggested_high."""
    ...

def test_price_history_discount_rate(db_session):
    """discount_rate = winning_price / budget_amount."""
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/week4/test_week4_migrations.py tests/week4/test_pricing_models.py -v`
Expected: FAIL (tables don't exist yet)

- [ ] **Step 3: Write migration**

```python
# alembic/versions/w004_add_pricing_tables.py
"""Add Week 4 pricing tables: cost_estimates, pricing_decisions, price_history"""
from alembic import op
import sqlalchemy as sa

revision = 'w004'
down_revision = 'w003'
branch_labels = None
depends_on = None

def upgrade():
    # cost_estimates
    op.create_table('cost_estimates',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False, default=1),
        sa.Column('food_cost', sa.Numeric(15,2), nullable=False),
        sa.Column('logistics_cost', sa.Numeric(15,2), nullable=False),
        sa.Column('labor_cost', sa.Numeric(15,2), nullable=False),
        sa.Column('management_cost', sa.Numeric(15,2), nullable=False),
        sa.Column('other_cost', sa.Numeric(15,2), nullable=False, default=0),
        sa.Column('total_cost', sa.Numeric(15,2), nullable=False),
        sa.Column('estimated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('estimate_reason', sa.Text(), nullable=True),
        sa.Column('is_confirmed', sa.Boolean(), default=False),
        sa.UniqueConstraint('project_id', 'version_number'),
    )

    # pricing_decisions
    op.create_table('pricing_decisions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cost_estimate_id', sa.Integer(), sa.ForeignKey('cost_estimates.id'), nullable=True),
        sa.Column('cost_base', sa.Numeric(15,2), nullable=False),
        sa.Column('system_suggested_low', sa.Numeric(15,2), nullable=False),
        sa.Column('system_suggested_high', sa.Numeric(15,2), nullable=False),
        sa.Column('system_suggested_optimal', sa.Numeric(15,2), nullable=True),
        sa.Column('finance_suggested_price', sa.Numeric(15,2), nullable=True),
        sa.Column('finance_suggestion_reason', sa.Text(), nullable=True),
        sa.Column('boss_final_price', sa.Numeric(15,2), nullable=False),
        sa.Column('boss_decision_reason', sa.Text(), nullable=True),
        sa.Column('deviation_from_system', sa.Numeric(5,4), nullable=True),
        sa.Column('deviation_reason_category', sa.String(50), nullable=True),
        sa.Column('budget_limit', sa.Numeric(15,2), nullable=True),
        sa.Column('is_under_limit', sa.Boolean(), nullable=True),
        sa.Column('limit_violation_warning', sa.Text(), nullable=True),
        sa.Column('game_theory_analysis', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), default='decided'),
    )

    # price_history
    op.create_table('price_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_type', sa.String(100), nullable=True),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('budget_amount', sa.Numeric(15,2), nullable=True),
        sa.Column('our_cost', sa.Numeric(15,2), nullable=True),
        sa.Column('our_bid_price', sa.Numeric(15,2), nullable=True),
        sa.Column('winning_price', sa.Numeric(15,2), nullable=True),
        sa.Column('winning_unit', sa.String(255), nullable=True),
        sa.Column('discount_rate', sa.Numeric(5,4), nullable=True),
        sa.Column('bid_date', sa.Date(), nullable=True),
        sa.Column('is_our_win', sa.Boolean(), nullable=True),
        sa.Column('data_source', sa.String(50), nullable=True),
    )

def downgrade():
    op.drop_table('price_history')
    op.drop_table('pricing_decisions')
    op.drop_table('cost_estimates')
```

- [ ] **Step 4: Write SQLAlchemy models**

```python
# app/models/pricing.py
from sqlalchemy import String, Integer, Boolean, ForeignKey, Numeric, Text, Date
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSON
from app.models.base import Base
from decimal import Decimal
from datetime import date

class CostEstimate(Base):
    __tablename__ = "cost_estimates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    food_cost: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=False)
    logistics_cost: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=False)
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=False)
    management_cost: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=False)
    other_cost: Mapped[Decimal] = mapped_column(Numeric(15,2), default=Decimal('0'))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=False)
    estimated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    estimate_reason: Mapped[str] = mapped_column(Text, nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

class PricingDecision(Base):
    __tablename__ = "pricing_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    cost_estimate_id: Mapped[int] = mapped_column(ForeignKey("cost_estimates.id"), nullable=True)
    cost_base: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=False)
    system_suggested_low: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=False)
    system_suggested_high: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=False)
    system_suggested_optimal: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=True)
    finance_suggested_price: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=True)
    finance_suggestion_reason: Mapped[str] = mapped_column(Text, nullable=True)
    boss_final_price: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=False)
    boss_decision_reason: Mapped[str] = mapped_column(Text, nullable=True)
    deviation_from_system: Mapped[Decimal] = mapped_column(Numeric(5,4), nullable=True)
    deviation_reason_category: Mapped[str] = mapped_column(String(50), nullable=True)
    budget_limit: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=True)
    is_under_limit: Mapped[bool] = mapped_column(Boolean, nullable=True)
    limit_violation_warning: Mapped[str] = mapped_column(Text, nullable=True)
    game_theory_analysis: Mapped[dict] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='decided')

class PriceHistory(Base):
    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_type: Mapped[str] = mapped_column(String(100), nullable=True)
    region: Mapped[str] = mapped_column(String(100), nullable=True)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=True)
    our_cost: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=True)
    our_bid_price: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=True)
    winning_price: Mapped[Decimal] = mapped_column(Numeric(15,2), nullable=True)
    winning_unit: Mapped[str] = mapped_column(String(255), nullable=True)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(5,4), nullable=True)
    bid_date: Mapped[date] = mapped_column(Date, nullable=True)
    is_our_win: Mapped[bool] = mapped_column(Boolean, nullable=True)
    data_source: Mapped[str] = mapped_column(String(50), nullable=True)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/week4/test_week4_migrations.py tests/week4/test_pricing_models.py -v`
Expected: PASS

- [ ] **Step 6: Verify Week 3 regression**

Run: `pytest tests/week3/ -v --tb=short`
Expected: 105/105 PASS

- [ ] **Step 7: Commit**

```bash
git add alembic/versions/w004_add_pricing_tables.py app/models/pricing.py tests/week4/test_week4_migrations.py tests/week4/test_pricing_models.py
git commit -m "feat(week4): add cost_estimates, pricing_decisions, price_history tables and models"
```

---

## Task 2: Cost Estimation Engine

**Files:**
- Create: `app/core/week4_pricing/cost_engine.py`
- Create: `tests/week4/test_cost_engine.py`

### Sub-Steps

- [ ] **Step 1: Write failing tests** (3 tests)
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Write implementation** (`CostEstimationEngine.breakdown_cost()`, `.estimate_from_history()`)
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

## Task 3: 博弈定价模型 (Pricing Game Theory Model)

**Files:**
- Create: `app/core/week4_pricing/game_theory.py`
- Create: `tests/week4/test_game_theory.py`

### Sub-Steps

- [ ] **Step 1: Write failing tests** (5 tests: aggressive/balanced/conservative scenarios, optimal=highest EV, relationship保底75%, cold-start降级)
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Write implementation** (`PricingGameTheoryModel.generate_price_scenarios()`, `.calculate_win_probability()`)
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

## Task 4: 拦截规则 (Pricing Intercept Rules)

**Files:**
- Create: `app/core/week4_pricing/intercept_rules.py`
- Create: `tests/week4/test_intercept_rules.py`

### Sub-Steps

- [ ] **Step 1: Write failing tests** (5 tests: 成本倒挂警告, 亏损定价拦截, 超限强制确认, 差异>5%强制原因, 正常定价通过)
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Write implementation** (`PricingInterceptRules.check_cost_vs_budget()`, `.check_final_price()`, `.check_deviation()`)
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

## Task 5: Pydantic Schemas

**Files:**
- Create: `app/schemas/week4.py`
- Create: `tests/week4/test_week4_schemas.py`

### Sub-Steps

- [ ] **Step 1: Write failing tests** (3 tests)
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Write schemas** (`CostEstimateCreate`, `CostEstimateResponse`, `PriceScenario`, `PricingCalculationResponse`, `PricingDecisionCreate`, `PricingDecisionResponse`)
- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**

---

## Task 6: API Endpoints

**Files:**
- Create: `app/api/v1/endpoints/pricing.py`
- Modify: `app/main.py` (register router)
- Create: `tests/week4/test_pricing_api.py`

### Sub-Steps

- [ ] **Step 1: Write failing tests** (6 tests: create cost, confirm cost, generate scenarios, submit decision, loss rejected, over-limit confirmation)
- [ ] **Step 2: Run tests to verify they fail**
- [ ] **Step 3: Write endpoints** (5 endpoints: POST cost-estimate, POST confirm, POST pricing-calculations, POST pricing-decisions, GET pricing-dashboard)
- [ ] **Step 4: Register router in main.py**
- [ ] **Step 5: Run tests to verify they pass**
- [ ] **Step 6: Commit**

---

## Final Verification

- [ ] Run `pytest tests/week4/ -v` → all Week 4 tests PASS
- [ ] Run `pytest tests/week3/ -v` → 105/105 PASS (regression guarantee)

---

## Summary

| Component | Files | Tests |
|-----------|-------|-------|
| Migration + Models | `w004_*.py` + `pricing.py` | ~11 |
| Cost Engine | `cost_engine.py` | 3 |
| Game Theory | `game_theory.py` | 5 |
| Intercept Rules | `intercept_rules.py` | 5 |
| Schemas | `week4.py` | 3 |
| API Endpoints | `pricing.py` | 6 |
| **Total** | | **~33** |

**No new external dependencies** — uses Python stdlib `decimal`, SQLAlchemy, FastAPI, Alembic (consistent with existing patterns).

**Week 3 regression**: 105/105 tests must remain green throughout.
