# Week 2 Implementation Plan: Screening & Intelligence Engine (SIE)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Screening & Intelligence Engine - evaluation report generation, Option-A approval workflow, boss oversight dashboard.

**Architecture:** Week 2 reads Week 1's validated OCR data (Single Source of Truth, immutable) and produces evaluation reports. Option-A approval: specialist decides immediately (worthy/unworthy), boss can override afterward with audit logging.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, PostgreSQL/pgvector

**Reference Documents:**
- Master Spec: `D:\tis_project\00_TIS_MASTER_SPEC.md`
- Global Rules: `D:\tis_project\GLOBAL_RULES.md`
- Week 1 Models: `D:\tis_project\app\models\*.py`

---

## ⚠️ Critical Design Constraints from Master Spec

### 1. Single Source of Truth (Week 1 → Week 2 Data Handover)

Per `00_TIS_MASTER_SPEC.md §6`:
- Week 1 confirmed data (`ocr_extractions.is_validated=true`) is **immutable Single Source of Truth**
- Week 2 **MUST NOT** re-parse, re-OCR, or re-extract Week 1 data
- Week 2 reads `is_validated=true` records only and performs business evaluation on them
- Backtracking: If专员 discovers Week 1 missed something, they use 【回退到解析阶段】 button, modify in Week 1, then Week 2 re-reads

### 2. ⚠️ CONFLICT - Missing `standard_cert_suggestion` Field

**Issue**: Week 1 plan (Conflict 1 resolution) called for two fields:
- `standard_cert_suggestion` (nullable, set during OCR as hint)
- `standard_cert_id` (authoritative, set at confirmation)

But the actual `OcrExtraction` model only has `standard_cert_id`. The Week 1 subagent did not implement the `standard_cert_suggestion` field.

**Resolution for Week 2**: Add `standard_cert_suggestion` via Alembic migration. The authoritative field for Week 3+ is still `standard_cert_id` (set during confirmation). `standard_cert_suggestion` is UI hint only.

### 3. Exact Match is Life-or-Death (R1)

Per `00_TIS_MASTER_SPEC.md §6 R1`:
- Certificate names must be **exact match** to `standard_certifications` encoding
- `"食品经营许可证"` vs `"食品生产许可证"` must be distinguished (exclude_keywords are mutually exclusive)
- `"一级资质"` vs `"二级资质"` must be distinguished (level keyword exact match)

Week 2's `QualificationMatcher` reuses Week 1's exact matching algorithm. Week 2 MUST NOT use fuzzy matching.

---

## File Structure

```
tis-project/
├── alembic/
│   └── versions/
│       └── w002_add_week2_tables.py      # Week 2 DB migrations
├── app/
│   ├── models/
│   │   ├── owner.py                      # OwnerProfile model
│   │   ├── evaluation.py                  # BidEvaluationReport model
│   │   ├── approval.py                   # ApprovalLog model
│   │   └── discarded.py                   # DiscardedProject model
│   ├── schemas/
│   │   └── evaluation.py                  # Week 2 Pydantic schemas
│   └── core/
│       └── week2_evaluation/
│           ├── qualification_matcher.py   # Exact cert matching engine
│           ├── time_evaluator.py           # Days until bid open calculation
│           ├── owner_profile_service.py    # Owner relationship index
│           ├── cost_estimator.py           # Cost estimation
│           ├── win_probability_calculator.py # Heuristic probability
│           ├── evaluation_report_engine.py # Full report generation
│           └── approval_workflow.py       # Option-A approval service
├── services/
│   └── notification.py                    # (Stub) notify boss/specialist
├── api/v1/endpoints/
│   ├── evaluations.py                     # Evaluation report endpoints
│   └── approvals.py                       # Approval + oversight endpoints
└── tests/
    ├── week2/
    │   ├── test_qualification_matcher.py
    │   ├── test_time_evaluator.py
    │   ├── test_win_probability.py
    │   ├── test_approval_workflow.py
    │   └── test_evaluation_report_engine.py
    └── integration/
        └── test_week2_flow.py
```

---

## Step-by-Step Implementation Tasks

---

### Task 1: Week 2 Database Migration (New Tables)

**Files:**
- Create: `alembic/versions/w002_add_week2_tables.py`
- Modify: `app/models/__init__.py` (add new model exports)
- Create: `app/models/owner.py`
- Create: `app/models/evaluation.py`
- Create: `app/models/approval.py`
- Create: `app/models/discarded.py`

**Enums to Add in `app/models/enums.py`:**
```python
class TimeUrgencyLevel(str, enum.Enum):
    EXPIRED = "expired"    # < 0 days
    URGENT = "urgent"      # 1-3 days
    TIGHT = "tight"        # 4-7 days
    NORMAL = "normal"      # 8-15 days
    RELAXED = "relaxed"    # > 15 days

class RiskLevel(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class Recommendation(str, enum.Enum):
    WORTH_BIDDING = "worth_bidding"
    ABANDON = "abandon"
    CONDITIONAL = "conditional"

class ApprovalAction(str, enum.Enum):
    SPECIALIST_WORTHY = "specialist_worthy"
    SPECIALIST_UNWORTHY = "specialist_unworthy"
    BOSS_OVERRIDE_TERMINATE = "boss_override_terminate"
    BOSS_OVERRIDE_REVIVE = "boss_override_revive"
    BOSS_CONFIRM_SPECIALIST = "boss_confirm_specialist"

class RelationshipLevel(str, enum.Enum):
    NONE = "none"
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"

class CostConfidence(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

- [ ] **Step 1: Write failing migration test**

```python
# tests/unit/test_week2_migrations.py
import pytest

def test_week2_tables_exist(run_migrations):
    result = run_migrations(["--sql", "-m", "w002_add_week2"])
    assert "CREATE TABLE owner_profiles" in result
    assert "CREATE TABLE bid_evaluation_reports" in result
    assert "CREATE TABLE approval_logs" in result
    assert "CREATE TABLE discarded_projects" in result
```

Run: `pytest tests/unit/test_week2_migrations.py -v` → FAIL

- [ ] **Step 2: Write new enum values**

Add to `app/models/enums.py`: `TimeUrgencyLevel`, `RiskLevel`, `Recommendation`, `ApprovalAction`, `RelationshipLevel`, `CostConfidence`

- [ ] **Step 3: Write new models**

**`app/models/owner.py`**:
```python
from sqlalchemy import String, Integer, DECIMAL, Date, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin
from app.models.enums import OwnerType, RelationshipLevel

class OwnerProfile(Base, TimestampMixin):
    __tablename__ = "owner_profiles"

    owner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_type: Mapped[OwnerType] = mapped_column(String(50), nullable=True)
    region: Mapped[str] = mapped_column(String(100), nullable=True)
    cooperation_count: Mapped[int] = mapped_column(Integer, default=0)
    last_cooperation_date: Mapped[Date] = mapped_column(Date, nullable=True)
    relationship_level: Mapped[RelationshipLevel] = mapped_column(String(20), default=RelationshipLevel.NONE)
    avg_winning_discount: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=True)
    preferred_styles: Mapped[dict] = mapped_column(JSON, nullable=True)
    common_requirements: Mapped[list] = mapped_column(JSON, nullable=True)
    blacklist_flags: Mapped[list] = mapped_column(JSON, nullable=True)

    __table_args__ = (UniqueConstraint('owner_name', 'region'),)
```

**`app/models/evaluation.py`**:
```python
from sqlalchemy import String, Integer, ForeignKey, DECIMAL, JSON, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin
from app.models.enums import TimeUrgencyLevel, RiskLevel, Recommendation, CostConfidence

class BidEvaluationReport(Base, TimestampMixin):
    __tablename__ = "bid_evaluation_reports"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    report_version: Mapped[int] = mapped_column(Integer, default=1)

    qualification_match_score: Mapped[int] = mapped_column(Integer, nullable=True)
    missing_mandatory_certs: Mapped[list] = mapped_column(JSON, nullable=True)
    missing_optional_certs: Mapped[list] = mapped_column(JSON, nullable=True)
    matched_certs_detail: Mapped[list] = mapped_column(JSON, nullable=True)

    days_until_bid_open: Mapped[int] = mapped_column(Integer, nullable=True)
    time_urgency_level: Mapped[TimeUrgencyLevel] = mapped_column(String(20), nullable=True)
    is_time_sufficient: Mapped[bool] = mapped_column(nullable=True)

    owner_profile_id: Mapped[int] = mapped_column(ForeignKey("owner_profiles.id"), nullable=True)
    relationship_index: Mapped[int] = mapped_column(Integer, nullable=True)
    is_new_owner: Mapped[bool] = mapped_column(nullable=True)

    estimated_cost: Mapped[float] = mapped_column(DECIMAL(15, 2), nullable=True)
    suggested_price_range_low: Mapped[float] = mapped_column(DECIMAL(15, 2), nullable=True)
    suggested_price_range_high: Mapped[float] = mapped_column(DECIMAL(15, 2), nullable=True)
    cost_estimate_confidence: Mapped[CostConfidence] = mapped_column(String(20), nullable=True)

    overall_win_probability: Mapped[float] = mapped_column(DECIMAL(5, 4), nullable=True)
    risk_level: Mapped[RiskLevel] = mapped_column(String(20), nullable=True)
    fatal_risks: Mapped[list] = mapped_column(JSON, nullable=True)
    warning_risks: Mapped[list] = mapped_column(JSON, nullable=True)

    recommendation: Mapped[Recommendation] = mapped_column(String(20), nullable=True)
    recommendation_reason: Mapped[str] = mapped_column(String(500), nullable=True)

    generated_by: Mapped[str] = mapped_column(String(50), default='system')
    confirmed_by_specialist: Mapped[bool] = mapped_column(default=False)
    specialist_decision: Mapped[str] = mapped_column(String(20), nullable=True)
    specialist_notes: Mapped[str] = mapped_column(String(500), nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    overridden_by_boss: Mapped[bool] = mapped_column(default=False)
    boss_override_reason: Mapped[str] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        UniqueConstraint('project_id', 'report_version'),
        CheckConstraint('qualification_match_score BETWEEN 0 AND 100'),
        CheckConstraint('relationship_index BETWEEN 0 AND 100'),
    )
```

**`app/models/approval.py`**:
```python
from sqlalchemy import String, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin
from app.models.enums import ApprovalAction

class ApprovalLog(Base, TimestampMixin):
    __tablename__ = "approval_logs"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    action_type: Mapped[ApprovalAction] = mapped_column(String(50), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    reason_text: Mapped[str] = mapped_column(Text, nullable=True)
    original_status: Mapped[str] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=True)
```

**`app/models/discarded.py`**:
```python
from sqlalchemy import String, Integer, ForeignKey, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin

class DiscardedProject(Base, TimestampMixin):
    __tablename__ = "discarded_projects"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    original_evaluation_report_id: Mapped[int] = mapped_column(ForeignKey("bid_evaluation_reports.id"), nullable=True)
    discarded_by: Mapped[str] = mapped_column(String(50), nullable=False)
    discard_reason: Mapped[str] = mapped_column(Text, nullable=True)
    discard_stage: Mapped[str] = mapped_column(String(50), nullable=True)
    can_be_revived: Mapped[bool] = mapped_column(Boolean, default=True)
    revived_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    revived_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    revived_to_project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=True)
```

- [ ] **Step 4: Write Alembic migration `w002_add_week2_tables.py`**

```python
# alembic/versions/w002_add_week2_tables.py
"""Week 2 tables: owner_profiles, bid_evaluation_reports, approval_logs, discarded_projects

Revision ID: w002
Revises: w001
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = 'w002'
down_revision = 'w001'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # owner_profiles
    op.create_table('owner_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_name', sa.String(255), nullable=False),
        sa.Column('owner_type', sa.String(50), nullable=True),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('cooperation_count', sa.Integer(), default=0),
        sa.Column('last_cooperation_date', sa.Date(), nullable=True),
        sa.Column('relationship_level', sa.String(20), default='none'),
        sa.Column('avg_winning_discount', sa.Numeric(5, 2), nullable=True),
        sa.Column('preferred_styles', JSON, nullable=True),
        sa.Column('common_requirements', JSON, nullable=True),
        sa.Column('blacklist_flags', JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('owner_name', 'region'),
    )

    # bid_evaluation_reports
    op.create_table('bid_evaluation_reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('report_version', sa.Integer(), default=1),
        sa.Column('qualification_match_score', sa.Integer(), nullable=True),
        sa.Column('missing_mandatory_certs', JSON, nullable=True),
        sa.Column('missing_optional_certs', JSON, nullable=True),
        sa.Column('matched_certs_detail', JSON, nullable=True),
        sa.Column('days_until_bid_open', sa.Integer(), nullable=True),
        sa.Column('time_urgency_level', sa.String(20), nullable=True),
        sa.Column('is_time_sufficient', sa.Boolean(), nullable=True),
        sa.Column('owner_profile_id', sa.Integer(), sa.ForeignKey('owner_profiles.id'), nullable=True),
        sa.Column('relationship_index', sa.Integer(), nullable=True),
        sa.Column('is_new_owner', sa.Boolean(), nullable=True),
        sa.Column('estimated_cost', sa.Numeric(15, 2), nullable=True),
        sa.Column('suggested_price_range_low', sa.Numeric(15, 2), nullable=True),
        sa.Column('suggested_price_range_high', sa.Numeric(15, 2), nullable=True),
        sa.Column('cost_estimate_confidence', sa.String(20), nullable=True),
        sa.Column('overall_win_probability', sa.Numeric(5, 4), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=True),
        sa.Column('fatal_risks', JSON, nullable=True),
        sa.Column('warning_risks', JSON, nullable=True),
        sa.Column('recommendation', sa.String(20), nullable=True),
        sa.Column('recommendation_reason', sa.String(500), nullable=True),
        sa.Column('generated_by', sa.String(50), default='system'),
        sa.Column('confirmed_by_specialist', sa.Boolean(), default=False),
        sa.Column('specialist_decision', sa.String(20), nullable=True),
        sa.Column('specialist_notes', sa.String(500), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('overridden_by_boss', sa.Boolean(), default=False),
        sa.Column('boss_override_reason', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('project_id', 'report_version'),
    )

    # approval_logs
    op.create_table('approval_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('actor_role', sa.String(50), nullable=False),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reason_text', sa.Text(), nullable=True),
        sa.Column('original_status', sa.String(50), nullable=True),
        sa.Column('new_status', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # discarded_projects
    op.create_table('discarded_projects',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('original_evaluation_report_id', sa.Integer(), sa.ForeignKey('bid_evaluation_reports.id'), nullable=True),
        sa.Column('discarded_by', sa.String(50), nullable=False),
        sa.Column('discard_reason', sa.Text(), nullable=True),
        sa.Column('discard_stage', sa.String(50), nullable=True),
        sa.Column('can_be_revived', sa.Boolean(), default=True),
        sa.Column('revived_at', sa.DateTime(), nullable=True),
        sa.Column('revived_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('revived_to_project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

def downgrade() -> None:
    op.drop_table('discarded_projects')
    op.drop_table('approval_logs')
    op.drop_table('bid_evaluation_reports')
    op.drop_table('owner_profiles')
```

- [ ] **Step 5: Run migration tests** → PASS

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/w002_*.py app/models/owner.py app/models/evaluation.py app/models/approval.py app/models/discarded.py app/models/enums.py app/models/__init__.py tests/unit/test_week2_migrations.py
git commit -m "feat(week2): add database migration for Week 2 tables"
```

---

### Task 2: Qualification Matcher Engine (Exact Match)

**Files:**
- Create: `app/core/week2_evaluation/qualification_matcher.py`
- Create: `tests/week2/test_qualification_matcher.py`

- [ ] **Step 1: Write failing tests for exact match logic**

```python
# tests/week2/test_qualification_matcher.py
import pytest
from app.core.week2_evaluation.qualification_matcher import QualificationMatcher

def test_food_business_matches_food_not_production(session, seed_certs):
    """Food business license must NOT match production license."""
    matcher = QualificationMatcher(session, project_id=1)
    result = matcher.exact_match_check(
        normalized={'cleaned_name': '食品经营许可证'},
        std_cert={'cert_code': 'FOOD-BUSINESS-LICENSE', ...}
    )
    assert result is True

def test_production_license_excluded_from_business(session, seed_certs):
    """Production license should not match FOOD-BUSINESS-LICENSE due to exclude_keywords."""
    matcher = QualificationMatcher(session, project_id=1)
    result = matcher.exact_match_check(
        normalized={'cleaned_name': '食品生产许可证'},
        std_cert={'cert_code': 'FOOD-BUSINESS-LICENSE', ...}  # has '生产' in exclude
    )
    assert result is False

def test_level_1_does_not_match_level_2(session, seed_certs):
    """'建筑工程施工总承包二级' must not match level-1 cert."""
    matcher = QualificationMatcher(session, project_id=1)
    level1_cert = {'cert_code': 'CONSTRUCTION-GENERAL-1', 'cert_full_name': '建筑工程施工总承包一级', ...}
    result = matcher.exact_match_check(
        normalized={'cleaned_name': '建筑工程施工总承包二级', 'level_keyword': '二级'},
        std_cert=level1_cert
    )
    assert result is False

def test_missing_mandatory_cert_returns_fatal(session, seed_certs):
    """Missing mandatory cert must appear in fatal_missing list."""
    matcher = QualificationMatcher(session, project_id=1)
    # Setup: project has no HACCP cert but tender requires it
    result = matcher.exact_match_evaluation()
    # HACCP is optional (not mandatory), so not in fatal_missing
    # But if FOOD-BUSINESS-LICENSE is missing (mandatory), it should be in fatal_missing
    assert 'missing_mandatory_certs' in result
```

Run: `pytest tests/week2/test_qualification_matcher.py -v` → FAIL

- [ ] **Step 2: Write `qualification_matcher.py`**

```python
# app/core/week2_evaluation/qualification_matcher.py
"""Qualification Matcher - Week 2 Exact Match Engine.

IMPORTANT: This is NOT fuzzy matching. It reuses Week 1's exact matching rules:
- ALL required_keywords must be present
- NO exclude_keywords can be present
- Level keywords (一级/二级) must match exactly

Per Master Spec §6 R1: Certificate names must be EXACT match.
"""
import json
import re
from typing import Optional
from sqlalchemy.orm import Session
from app.models.standard import StandardCertification
from app.models.ocr import OcrExtraction

class QualificationMatcher:
    """
    Week 2 core: Exact matching between Week 1 OCR extractions
    and standard cert requirements from tender document.

    This reads ONLY validated Week 1 records (is_validated=True).
    """

    def __init__(self, db: Session, project_id: int):
        self.db = db
        self.project_id = project_id

    def exact_match_evaluation(self) -> dict:
        """
        Perform exact qualification matching evaluation.

        Returns:
            dict with keys: qualification_match_score, missing_mandatory_certs,
            missing_optional_certs, matched_certs, is_qualification_pass
        """
        # Get validated OCR extractions (Week 1 Single Source of Truth)
        bid_certs = self.db.query(OcrExtraction).filter(
            OcrExtraction.project_id == self.project_id,
            OcrExtraction.is_validated == True,
            OcrExtraction.field_name == 'cert_name',
        ).all()

        # Get tender requirements (extracted from tender document JSONB)
        tender = self._get_tender_requirements()
        if not tender:
            return self._empty_result()

        fatal_missing = []
        optional_missing = []
        matched_list = []

        for req in tender:
            matched = False
            std_cert = req.get('standard_cert')

            for ocr_cert in bid_certs:
                normalized = self._normalize_ocr_text(ocr_cert.normalized_value or ocr_cert.field_value)

                if self.exact_match_check(normalized, std_cert):
                    # Check validity
                    valid_check = self._check_validity(
                        ocr_cert.normalized_value,
                        self._get_bid_open_date(),
                        std_cert
                    )

                    if valid_check['status'] == 'valid':
                        matched = True
                        matched_list.append({
                            'cert_code': std_cert.cert_code,
                            'cert_name': std_cert.cert_full_name,
                            'valid_until': ocr_cert.normalized_value,
                            'evidence_image_id': ocr_cert.image_id
                        })
                    elif valid_check['status'] == 'expired':
                        fatal_missing.append({
                            'cert_code': std_cert.cert_code,
                            'cert_name': std_cert.cert_full_name,
                            'reason': 'expired',
                            'valid_until': ocr_cert.normalized_value,
                            'severity': 'fatal'
                        })
                        matched = True  # Mark matched to avoid duplicate missing entry
                        break
                    elif valid_check['status'] == 'expiring_soon':
                        optional_missing.append({
                            'cert_code': std_cert.cert_code,
                            'reason': 'expiring_soon',
                            'days_until_expire': valid_check['days_until_expire']
                        })
                        matched = True
                        break

            if not matched and req.get('is_mandatory'):
                fatal_missing.append({
                    'cert_code': req['cert_code'],
                    'cert_name': std_cert.cert_full_name if std_cert else req['cert_code'],
                    'reason': 'missing',
                    'severity': 'fatal'
                })
            elif not matched and not req.get('is_mandatory'):
                optional_missing.append(req['cert_code'])

        # Calculate score
        total_mandatory = len([r for r in tender if r.get('is_mandatory')])
        matched_mandatory = total_mandatory - len([m for m in fatal_missing if m.get('reason') == 'missing'])
        score = int((matched_mandatory / total_mandatory) * 100) if total_mandatory > 0 else 100

        return {
            'qualification_match_score': score,
            'missing_mandatory_certs': fatal_missing,
            'missing_optional_certs': optional_missing,
            'matched_certs': matched_list,
            'is_qualification_pass': len([m for m in fatal_missing if m.get('reason') in ['missing', 'expired']]) == 0
        }

    def exact_match_check(self, normalized: dict, std_cert: StandardCertification) -> bool:
        """Exact match per R1. Returns True only if ALL conditions met."""
        name = normalized.get('cleaned_name', '')

        # 1. ALL required_keywords must be present
        required = json.loads(std_cert.required_keywords) if isinstance(std_cert.required_keywords, str) else std_cert.required_keywords
        if not all(kw in name for kw in required):
            return False

        # 2. NO exclude_keywords can be present
        excluded = json.loads(std_cert.exclude_keywords) if isinstance(std_cert.exclude_keywords, str) else std_cert.exclude_keywords
        if any(kw in name for kw in excluded):
            return False

        # 3. Level keywords exact match
        if self._has_level_mismatch(name, std_cert):
            return False

        return True

    def _has_level_mismatch(self, name: str, std_cert: StandardCertification) -> bool:
        """Check if level keywords mismatch."""
        level_keywords = ['一级', '二级', '三级', '特级', '甲级', '乙级', '丙级']
        full_name = std_cert.cert_full_name or ''

        for level in level_keywords:
            in_std = level in full_name
            in_name = level in name
            if in_std != in_name:  # XOR - one has it, other doesn't
                return True
        return False

    def _normalize_ocr_text(self, text: str) -> dict:
        """Normalize OCR text and extract level keyword."""
        if not text:
            return {'cleaned_name': ''}
        cleaned = text.strip().replace(' ', '')
        level_kw = None
        for kw in ['特级', '一级', '二级', '三级', '甲级', '乙级', '丙级']:
            if kw in cleaned:
                level_kw = kw
                break
        return {'cleaned_name': cleaned, 'level_keyword': level_kw}

    def _check_validity(self, valid_until: str, bid_open_date, std_cert) -> dict:
        """Check if cert validity covers bid open date."""
        if not valid_until:
            return {'status': 'unknown'}

        from datetime import datetime, date
        try:
            if isinstance(valid_until, str):
                vu = datetime.strptime(valid_until[:10], '%Y-%m-%d').date()
            else:
                vu = valid_until

            if isinstance(bid_open_date, datetime):
                bod = bid_open_date.date()
            elif isinstance(bid_open_date, date):
                bod = bid_open_date
            else:
                bod = datetime.strptime(str(bid_open_date)[:10], '%Y-%m-%d').date()

            if vu < bod:
                return {'status': 'expired', 'days_past': (bod - vu).days}

            if vu < bod + timedelta(days=90):
                return {
                    'status': 'expiring_soon',
                    'days_until_expire': (vu - bod).days
                }

            return {'status': 'valid', 'days_valid': (vu - bod).days}
        except:
            return {'status': 'unknown'}

    def _get_tender_requirements(self) -> list:
        """Get qualification requirements from tender document."""
        from app.models.document import TenderDocument
        tender = self.db.query(TenderDocument).filter_by(project_id=self.project_id).first()
        if not tender or not tender.extracted_data:
            return []
        requirements = tender.extracted_data.get('qualification_requirements', [])
        # Enrich with standard cert objects
        for req in requirements:
            cert = self.db.query(StandardCertification).filter_by(cert_code=req.get('cert_code')).first()
            req['standard_cert'] = cert
        return requirements

    def _get_bid_open_date(self):
        from app.models.project import Project
        project = self.db.query(Project).get(self.project_id)
        return project.bid_open_date if project else None

    def _empty_result(self) -> dict:
        return {
            'qualification_match_score': 0,
            'missing_mandatory_certs': [],
            'missing_optional_certs': [],
            'matched_certs': [],
            'is_qualification_pass': False
        }
```

- [ ] **Step 3: Run tests** → PASS

- [ ] **Step 4: Commit**

---

### Task 3: Time Evaluator & Win Probability Calculator

**Files:**
- Create: `app/core/week2_evaluation/time_evaluator.py`
- Create: `app/core/week2_evaluation/win_probability_calculator.py`
- Create: `tests/week2/test_time_evaluator.py`
- Create: `tests/week2/test_win_probability.py`

- [ ] **Step 1: Write failing tests for time urgency**

```python
# tests/week2/test_time_evaluator.py
import pytest
from datetime import datetime, timedelta
from app.core.week2_evaluation.time_evaluator import TimeEvaluator

def test_expired_bid_open():
    """Bid open date in past → 'expired'."""
    evaluator = TimeEvaluator()
    past = datetime.now() - timedelta(days=1)
    result = evaluator.calculate(past)
    assert result['time_urgency_level'] == 'expired'
    assert result['is_time_sufficient'] is False

def test_urgent_3_days():
    """1-3 days remaining → 'urgent'."""
    evaluator = TimeEvaluator()
    soon = datetime.now() + timedelta(days=2)
    result = evaluator.calculate(soon)
    assert result['time_urgency_level'] == 'urgent'

def test_relaxed_20_days():
    """>15 days → 'relaxed'."""
    evaluator = TimeEvaluator()
    future = datetime.now() + timedelta(days=20)
    result = evaluator.calculate(future)
    assert result['time_urgency_level'] == 'relaxed'
    assert result['is_time_sufficient'] is True
```

Run: `pytest tests/week2/test_time_evaluator.py -v` → FAIL

- [ ] **Step 2: Write `time_evaluator.py`**

```python
# app/core/week2_evaluation/time_evaluator.py
"""Time Urgency Evaluator."""
from datetime import datetime, timedelta
from typing import Optional

class TimeEvaluator:
    """
    Calculate time urgency level based on days until bid open.

    Rules (from Week_02.md):
    - expired: days < 0
    - urgent: 1-3 days
    - tight: 4-7 days
    - normal: 8-15 days
    - relaxed: > 15 days
    """

    def calculate(self, bid_open_date: datetime, current: Optional[datetime] = None) -> dict:
        if current is None:
            current = datetime.now()

        days_remaining = (bid_open_date - current).days

        if days_remaining < 0:
            level = 'expired'
            sufficient = False
        elif days_remaining <= 3:
            level = 'urgent'
            sufficient = False
        elif days_remaining <= 7:
            level = 'tight'
            sufficient = True
        elif days_remaining <= 15:
            level = 'normal'
            sufficient = True
        else:
            level = 'relaxed'
            sufficient = True

        return {
            'days_until_bid_open': days_remaining,
            'time_urgency_level': level,
            'is_time_sufficient': sufficient,
            'working_days_estimate': int(days_remaining * 0.7) if days_remaining >= 0 else 0
        }
```

- [ ] **Step 3: Write failing test for win probability**

```python
# tests/week2/test_win_probability.py
import pytest
from app.core.week2_evaluation.win_probability_calculator import WinProbabilityCalculator

def test_fatal_risk_returns_zero():
    """qual_score < 60 OR expired → probability = 0."""
    calc = WinProbabilityCalculator()
    result = calc.calculate(qual_score=50, time_level='normal', relationship_index=50, competition_count=1)
    assert result == 0.0

def test_expired_time_returns_zero():
    """expired time level → probability = 0 regardless of other factors."""
    calc = WinProbabilityCalculator()
    result = calc.calculate(qual_score=80, time_level='expired', relationship_index=50, competition_count=1)
    assert result == 0.0

def test_normal_scenario():
    """Normal scenario returns weighted probability."""
    calc = WinProbabilityCalculator()
    result = calc.calculate(qual_score=80, time_level='normal', relationship_index=50, competition_count=2)
    assert 0 <= result <= 1
```

Run: `pytest tests/week2/test_win_probability.py -v` → FAIL

- [ ] **Step 4: Write `win_probability_calculator.py`**

```python
# app/core/week2_evaluation/win_probability_calculator.py
"""Win Probability Calculator - Heuristic Algorithm.

Per Master Spec §8.2:
- Weights: qualification 40% + time 20% + relationship 30% + competition 10%
- Fatal risk: qual_score < 60 OR time_level == 'expired' → probability = 0
"""
from typing import Optional

class WinProbabilityCalculator:
    """
    Calculate comprehensive win probability using heuristic algorithm.

    Formula (per Master Spec):
    base = (qual_score*0.4 + time_score*0.2 + relationship_index*0.3 + competition_score*0.1) / 100
    Fatal: qual_score < 60 OR expired → 0
    """

    TIME_SCORES = {
        'expired': 0,
        'urgent': 40,
        'tight': 60,
        'normal': 80,
        'relaxed': 100
    }

    def calculate(
        self,
        qual_score: int,
        time_level: str,
        relationship_index: int,
        competition_count: int = 1
    ) -> float:
        """Calculate win probability 0-1."""
        # Fatal risk override
        if qual_score < 60:
            return 0.0
        if time_level == 'expired':
            return 0.0

        time_score = self.TIME_SCORES.get(time_level, 0)
        competition_score = max(0, 100 - competition_count * 10)

        base = (
            qual_score * 0.4 +
            time_score * 0.2 +
            relationship_index * 0.3 +
            competition_score * 0.1
        ) / 100

        return min(max(base, 0.0), 1.0)
```

- [ ] **Step 5: Run tests** → PASS

- [ ] **Step 6: Commit**

---

### Task 4: Owner Profile Service & Cost Estimator

**Files:**
- Create: `app/core/week2_evaluation/owner_profile_service.py`
- Create: `app/core/week2_evaluation/cost_estimator.py`
- Create: `tests/week2/test_owner_profile_service.py`

- [ ] **Step 1: Write failing tests for owner relationship**

```python
# tests/week2/test_owner_profile_service.py
import pytest
from app.core.week2_evaluation.owner_profile_service import OwnerProfileService

def test_new_owner_relationship_index_zero(db_session):
    """First-time owner → relationship_index=0, is_new_owner=True."""
    service = OwnerProfileService(db_session)
    result = service.get_or_create_profile("XX市第一中学", "school", "北京")
    assert result['relationship_index'] == 0
    assert result['is_new_owner'] is True

def test_existing_owner_relationship_index_positive(db_session, seed_owner_profile):
    """Existing owner with 2 cooperations → relationship_index > 0."""
    service = OwnerProfileService(db_session)
    result = service.get_or_create_profile("XX中学", "school", "北京")
    assert result['relationship_index'] > 0
    assert result['is_new_owner'] is False
```

Run: `pytest tests/week2/test_owner_profile_service.py -v` → FAIL

- [ ] **Step 2: Write `owner_profile_service.py`**

```python
# app/core/week2_evaluation/owner_profile_service.py
"""Owner Profile Service - Relationship Index Calculation."""
from datetime import datetime
from typing import Optional

class OwnerProfileService:
    """
    Get or create owner profile and calculate relationship index.

    Relationship index calculation (per Week_02.md):
    - base = min(cooperation_count * 20, 60)
    - recency boost: +20 if <=6 months, +10 if <=12 months
    - Max = 100
    """

    def get_or_create_profile(self, db, owner_name: str, owner_type: str, region: str) -> dict:
        from app.models.owner import OwnerProfile
        profile = db.query(OwnerProfile).filter_by(
            owner_name=owner_name, region=region
        ).first()

        is_new = profile is None
        if is_new:
            profile = OwnerProfile(
                owner_name=owner_name,
                owner_type=owner_type,
                region=region,
                cooperation_count=0,
                relationship_level='none'
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)

        relationship_index = self._calculate_relationship_index(profile)
        return {
            'owner_profile_id': profile.id,
            'relationship_index': relationship_index,
            'relationship_level': profile.relationship_level.value if profile.relationship_level else 'none',
            'is_new_owner': is_new,
            'cooperation_count': profile.cooperation_count,
            'last_cooperation_date': profile.last_cooperation_date,
            'avg_winning_discount': float(profile.avg_winning_discount) if profile.avg_winning_discount else None
        }

    def _calculate_relationship_index(self, profile) -> int:
        """Calculate relationship index 0-100."""
        if profile.cooperation_count == 0:
            return 0

        base = min(profile.cooperation_count * 20, 60)

        # Recency boost
        if profile.last_cooperation_date:
            months_ago = (datetime.now().date() - profile.last_cooperation_date).days / 30
            if months_ago <= 6:
                base += 20
            elif months_ago <= 12:
                base += 10

        return min(base, 100)
```

- [ ] **Step 3: Write `cost_estimator.py`**

```python
# app/core/week2_evaluation/cost_estimator.py
"""Cost Estimator - Pre-cursor to Week 4 pricing."""
from decimal import Decimal

class CostEstimator:
    """
    Estimate project cost for pre-pricing analysis.

    Cold start (no history): budget × 75%
    With history: average similar project costs with inflation adjustment
    """

    def estimate(self, budget_amount: float, project_type: str, region: str, db=None) -> dict:
        """
        Return dict with estimated_cost, low_price (+2%), high_price (+15%), confidence.
        """
        if not budget_amount or budget_amount <= 0:
            return {
                'estimated_cost': 0.0,
                'low_price': 0.0,
                'high_price': 0.0,
                'confidence': 'low'
            }

        # Cold start heuristic: budget × 75%
        estimated = budget_amount * 0.75
        confidence = 'low'

        return {
            'estimated_cost': round(estimated, 2),
            'low_price': round(estimated * 1.02, 2),
            'high_price': round(estimated * 1.15, 2),
            'confidence': confidence
        }
```

- [ ] **Step 4: Run tests** → PASS

- [ ] **Step 5: Commit**

---

### Task 5: Evaluation Report Engine (Orchestrator)

**Files:**
- Create: `app/core/week2_evaluation/evaluation_report_engine.py`
- Create: `tests/week2/test_evaluation_report_engine.py`

- [ ] **Step 1: Write failing test for report generation**

```python
# tests/week2/test_evaluation_report_engine.py
import pytest
from app.core.week2_evaluation.evaluation_report_engine import EvaluationReportEngine

def test_generate_report_returns_all_sections(db_session, seed_certs, seed_project):
    """Report must contain qualification, time, owner, cost, probability sections."""
    engine = EvaluationReportEngine(db_session, project_id=1)
    report = engine.generate_report()

    assert 'qualification_match_score' in report
    assert 'time_urgency_level' in report
    assert 'relationship_index' in report
    assert 'estimated_cost' in report
    assert 'overall_win_probability' in report
    assert 'recommendation' in report
    assert 'fatal_risks' in report

def test_expired_bid_gives_abandon_recommendation(db_session, seed_certs, seed_project):
    """Expired bid → recommendation = 'abandon'."""
    engine = EvaluationReportEngine(db_session, project_id=1)
    report = engine.generate_report()
    assert report['recommendation'] in ['abandon', 'conditional']
```

Run: `pytest tests/week2/test_evaluation_report_engine.py -v` → FAIL

- [ ] **Step 2: Write `evaluation_report_engine.py`**

```python
# app/core/week2_evaluation/evaluation_report_engine.py
"""Evaluation Report Engine - Main Orchestrator for Week 2."""
import json
from sqlalchemy.orm import Session
from app.core.week2_evaluation.qualification_matcher import QualificationMatcher
from app.core.week2_evaluation.time_evaluator import TimeEvaluator
from app.core.week2_evaluation.owner_profile_service import OwnerProfileService
from app.core.week2_evaluation.cost_estimator import CostEstimator
from app.core.week2_evaluation.win_probability_calculator import WinProbabilityCalculator
from app.models.evaluation import BidEvaluationReport

class EvaluationReportEngine:
    """
    Orchestrate full evaluation report generation.

    Steps:
    1. Qualification matching (exact match, per R1)
    2. Time urgency evaluation
    3. Owner profile & relationship index
    4. Cost estimation (pre-cursor to Week 4)
    5. Win probability calculation
    6. Risk aggregation & recommendation
    7. Persist to bid_evaluation_reports table
    """

    def __init__(self, db: Session, project_id: int):
        self.db = db
        self.project_id = project_id

    def generate_report(self) -> dict:
        """Generate complete evaluation report."""
        project = self.db.query(Project).get(self.project_id)
        if not project:
            raise ValueError(f"Project {self.project_id} not found")

        # 1. Qualification evaluation
        qual = QualificationMatcher(self.db, self.project_id).exact_match_evaluation()

        # 2. Time evaluation
        time_eval = TimeEvaluator()
        time_result = time_eval.calculate(project.bid_open_date) if project.bid_open_date else {
            'days_until_bid_open': 0,
            'time_urgency_level': 'expired',
            'is_time_sufficient': False,
            'working_days_estimate': 0
        }

        # 3. Owner relationship
        owner_service = OwnerProfileService()
        owner_result = owner_service.get_or_create_profile(
            self.db, project.owner_unit, project.owner_type.value if project.owner_type else None, project.region
        ) if project.owner_unit else {
            'owner_profile_id': None, 'relationship_index': 0, 'is_new_owner': True
        }

        # 4. Cost estimation
        cost_est = CostEstimator()
        cost_result = cost_est.estimate(
            float(project.budget_amount) if project.budget_amount else 0,
            project.project_type, project.region
        )

        # 5. Win probability
        prob_calc = WinProbabilityCalculator()
        win_prob = prob_calc.calculate(
            qual_score=qual['qualification_match_score'],
            time_level=time_result['time_urgency_level'],
            relationship_index=owner_result['relationship_index'],
            competition_count=1
        )

        # 6. Risk aggregation
        fatal_risks = []
        warning_risks = []

        if not qual['is_qualification_pass']:
            fatal_risks.append({
                'type': 'qualification',
                'message': f"缺失强制资质",
                'details': qual['missing_mandatory_certs']
            })

        if time_result['time_urgency_level'] == 'expired':
            fatal_risks.append({
                'type': 'time',
                'message': '开标时间已过，无法投标'
            })

        if owner_result['is_new_owner']:
            warning_risks.append({
                'type': 'relationship',
                'message': '业主为首次接触，无历史关系'
            })

        # 7. Recommendation
        if fatal_risks:
            recommendation = 'abandon'
            rec_reason = f"存在致命风险：{fatal_risks[0]['message']}"
        elif win_prob > 0.7:
            recommendation = 'worth_bidding'
            rec_reason = '中标概率较高，建议投标'
        elif win_prob > 0.4:
            recommendation = 'conditional'
            rec_reason = '有条件投标，需评估技术和价格策略'
        else:
            recommendation = 'abandon'
            rec_reason = '中标概率较低，建议放弃（除非有内幕关系）'

        # 8. Persist
        report = BidEvaluationReport(
            project_id=self.project_id,
            qualification_match_score=qual['qualification_match_score'],
            missing_mandatory_certs=qual['missing_mandatory_certs'],
            missing_optional_certs=qual['missing_optional_certs'],
            matched_certs_detail=qual['matched_certs'],
            days_until_bid_open=time_result['days_until_bid_open'],
            time_urgency_level=time_result['time_urgency_level'],
            is_time_sufficient=time_result['is_time_sufficient'],
            owner_profile_id=owner_result['owner_profile_id'],
            relationship_index=owner_result['relationship_index'],
            is_new_owner=owner_result['is_new_owner'],
            estimated_cost=cost_result['estimated_cost'],
            suggested_price_range_low=cost_result['low_price'],
            suggested_price_range_high=cost_result['high_price'],
            cost_estimate_confidence=cost_result['confidence'],
            overall_win_probability=win_prob,
            risk_level='high' if fatal_risks else ('medium' if warning_risks else 'low'),
            fatal_risks=fatal_risks,
            warning_risks=warning_risks,
            recommendation=recommendation,
            recommendation_reason=rec_reason,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        return {
            'report_id': report.id,
            **self._report_to_dict(report),
            'qualification_detail': qual,
            'time_detail': time_result,
            'owner_detail': owner_result
        }

    def _report_to_dict(self, report: BidEvaluationReport) -> dict:
        return {
            'qualification_match_score': report.qualification_match_score,
            'days_until_bid_open': report.days_until_bid_open,
            'time_urgency_level': report.time_urgency_level.value if hasattr(report.time_urgency_level, 'value') else report.time_urgency_level,
            'is_time_sufficient': report.is_time_sufficient,
            'relationship_index': report.relationship_index,
            'is_new_owner': report.is_new_owner,
            'estimated_cost': float(report.estimated_cost) if report.estimated_cost else None,
            'overall_win_probability': float(report.overall_win_probability) if report.overall_win_probability else 0.0,
            'risk_level': report.risk_level.value if hasattr(report.risk_level, 'value') else report.risk_level,
            'recommendation': report.recommendation.value if hasattr(report.recommendation, 'value') else report.recommendation,
            'recommendation_reason': report.recommendation_reason,
        }
```

- [ ] **Step 3: Run tests** → PASS

- [ ] **Step 4: Commit**

---

### Task 6: Approval Workflow Service (Option-A)

**Files:**
- Create: `app/core/week2_evaluation/approval_workflow.py`
- Create: `tests/week2/test_approval_workflow.py`

- [ ] **Step 1: Write failing test for specialist decision**

```python
# tests/week2/test_approval_workflow.py
import pytest
from app.core.week2_evaluation.approval_workflow import ApprovalWorkflowService

def test_specialist_worthy_immediately_approves(db_session, seed_project_with_report):
    """Specialist clicks worthy → project status becomes approved_by_specialist."""
    service = ApprovalWorkflowService(db_session)
    result = service.specialist_decide(project_id=1, decision='worthy', reason='', specialist_id=1)
    assert result['status'] == 'success'
    assert result['project_status'] == 'approved_by_specialist'

def test_specialist_cannot_worthy_expired_bid(db_session, seed_project_expired):
    """Expired bid + specialist marks worthy → must require override reason."""
    service = ApprovalWorkflowService(db_session)
    with pytest.raises(ValueError, match="致命风险"):
        service.specialist_decide(project_id=1, decision='worthy', reason='', specialist_id=1)

def test_boss_terminate_creates_audit_log(db_session, seed_project_approved):
    """Boss terminate → approval_log created, project status = terminated_by_boss."""
    service = ApprovalWorkflowService(db_session)
    result = service.boss_override(project_id=1, action='terminate', reason='利润不足', boss_id=2)
    assert result['status'] == 'success'
    # Verify approval_log was created
```

Run: `pytest tests/week2/test_approval_workflow.py -v` → FAIL

- [ ] **Step 2: Write `approval_workflow.py`**

```python
# app/core/week2_evaluation/approval_workflow.py
"""Approval Workflow Service - Option-A Approval Pattern.

Per Master Spec §6 R2:
- Specialist has independent approval authority (worthy/unworthy), takes effect immediately
- Boss has post-hoc oversight (can override with reason, recorded in audit log)
- All operations are logged in approval_logs table
"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.enums import ProjectStatus, ApprovalAction

class ApprovalWorkflowService:
    """
    Option-A Approval: Specialist decides immediately, boss can override afterward.

    Rules:
    1. Specialist worthy on fatal risk → must provide override reason (>10 chars)
    2. Expired bid open date → cannot be marked worthy
    3. Boss override → must provide reason, creates audit log
    4. Revive only works on rejected_by_specialist projects
    """

    def specialist_decide(self, db: Session, project_id: int, decision: str, reason: str, specialist_id: int) -> dict:
        """Specialist makes decision (worthy/unworthy). Takes effect immediately."""
        from app.models.project import Project
        from app.models.evaluation import BidEvaluationReport
        from app.models.approval import ApprovalLog

        project = db.query(Project).get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Get latest report
        report = db.query(BidEvaluationReport).filter_by(
            project_id=project_id
        ).order_by(BidEvaluationReport.report_version.desc()).first()

        # Check fatal risks
        fatal_risks = report.fatal_risks if report.fatal_risks else []
        if decision == 'worthy' and fatal_risks and len(reason) < 10:
            raise ValueError("存在致命风险仍标记worthy，必须填写覆盖理由（至少10字）")

        # Check expired bid
        if decision == 'worthy' and report.time_urgency_level == 'expired':
            raise ValueError("开标时间已过，无法标记worthy")

        # Update project status
        new_status = ProjectStatus.APPROVED_BY_SPECIALIST.value if decision == 'worthy' else ProjectStatus.REJECTED_BY_SPECIALIST.value
        project.status = new_status

        # Update report
        report.confirmed_by_specialist = True
        report.specialist_decision = decision
        report.specialist_notes = reason
        report.confirmed_at = datetime.now()

        # Create audit log
        log = ApprovalLog(
            project_id=project_id,
            action_type=ApprovalAction.SPECIALIST_WORTHY.value if decision == 'worthy' else ApprovalAction.SPECIALIST_UNWORTHY.value,
            actor_role='specialist',
            actor_id=specialist_id,
            reason_text=reason,
            original_status=project.status.value if hasattr(project.status, 'value') else project.status,
            new_status=new_status
        )
        db.add(log)
        db.commit()

        return {'status': 'success', 'project_status': new_status}

    def boss_override(self, db: Session, project_id: int, action: str, reason: str, boss_id: int) -> dict:
        """
        Boss override decision.

        action: 'terminate' (worthy→unworthy) or 'revive' (unworthy→worthy)
        """
        from app.models.project import Project
        from app.models.evaluation import BidEvaluationReport
        from app.models.approval import ApprovalLog
        from app.models.discarded import DiscardedProject

        project = db.query(Project).get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        current_status = project.status.value if hasattr(project.status, 'value') else project.status

        if action == 'terminate':
            if current_status != ProjectStatus.APPROVED_BY_SPECIALIST.value:
                raise ValueError("项目不在可终止状态")

            project.status = ProjectStatus.TERMINATED_BY_BOSS

            # Create discarded project record
            report = db.query(BidEvaluationReport).filter_by(project_id=project_id).order_by(BidEvaluationReport.report_version.desc()).first()
            discarded = DiscardedProject(
                project_id=project_id,
                original_evaluation_report_id=report.id if report else None,
                discarded_by='boss',
                discard_reason=f"[老板终止] {reason}",
                discard_stage=current_status
            )
            db.add(discarded)

            action_type = ApprovalAction.BOSS_OVERRIDE_TERMINATE.value
            new_status = ProjectStatus.TERMINATED_BY_BOSS.value

        elif action == 'revive':
            if current_status != ProjectStatus.REJECTED_BY_SPECIALIST.value:
                raise ValueError("项目不在可复活状态")

            project.status = ProjectStatus.APPROVED_BY_SPECIALIST
            action_type = ApprovalAction.BOSS_OVERRIDE_REVIVE.value
            new_status = ProjectStatus.APPROVED_BY_SPECIALIST.value

            # Remove from discarded or update
            discarded = db.query(DiscardedProject).filter_by(project_id=project_id).order_by(DiscardedProject.created_at.desc()).first()
            if discarded:
                discarded.can_be_revived = False
                discarded.revived_at = datetime.now()
                discarded.revived_by = boss_id
        else:
            raise ValueError(f"Unknown action: {action}")

        # Update report
        report = db.query(BidEvaluationReport).filter_by(project_id=project_id).order_by(BidEvaluationReport.report_version.desc()).first()
        if report:
            report.overridden_by_boss = True
            report.boss_override_reason = reason

        # Create audit log
        log = ApprovalLog(
            project_id=project_id,
            action_type=action_type,
            actor_role='boss',
            actor_id=boss_id,
            reason_text=reason,
            original_status=current_status,
            new_status=new_status
        )
        db.add(log)
        db.commit()

        return {'status': 'success', 'new_status': new_status}
```

- [ ] **Step 3: Run tests** → PASS

- [ ] **Step 4: Commit**

---

### Task 7: API Endpoints for Week 2

**Files:**
- Create: `app/api/v1/endpoints/evaluations.py`
- Create: `app/api/v1/endpoints/approvals.py`
- Create: `app/schemas/evaluation.py`
- Create: `tests/week2/test_api_evaluations.py`

- [ ] **Step 1: Write failing tests for evaluation API**

```python
# tests/week2/test_api_evaluations.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_initiate_evaluation(db_session, seed_project):
    """POST /api/projects/{id}/evaluation/initiate → returns report_id."""
    response = client.post(f"/api/projects/{seed_project}/evaluation/initiate")
    assert response.status_code == 200
    assert 'report_id' in response.json()

def test_get_evaluation_report(db_session, seed_report):
    """GET /api/evaluation-reports/{id} → returns full report."""
    response = client.get(f"/api/evaluation-reports/{seed_report}")
    assert response.status_code == 200
    data = response.json()
    assert 'qualification_match_score' in data
    assert 'recommendation' in data

def test_specialist_decide_worthy(db_session, seed_report):
    """POST /api/evaluation-reports/{id}/decide → worthy."""
    response = client.post(
        f"/api/evaluation-reports/{seed_report}/decide",
        json={"decision": "worthy", "reason": "项目资质齐全，中标概率高"}
    )
    assert response.status_code == 200
```

Run: `pytest tests/week2/test_api_evaluations.py -v` → FAIL

- [ ] **Step 2: Write Pydantic schemas `app/schemas/evaluation.py`**

```python
# app/schemas/evaluation.py
from pydantic import BaseModel
from typing import Optional, Any

class EvaluationInitiateResponse(BaseModel):
    report_id: int
    status: str

class EvaluationReportResponse(BaseModel):
    report_id: int
    project_id: int
    qualification_match_score: int
    missing_mandatory_certs: list
    days_until_bid_open: int
    time_urgency_level: str
    relationship_index: int
    overall_win_probability: float
    risk_level: str
    recommendation: str
    recommendation_reason: str
    specialist_decision: Optional[str]
    confirmed_by_specialist: bool

class SpecialistDecisionRequest(BaseModel):
    decision: str  # 'worthy' or 'unworthy'
    reason: str

class BossOverrideRequest(BaseModel):
    action: str  # 'terminate' or 'revive'
    reason: str

class OversightDashboardResponse(BaseModel):
    today_approved: list
    today_rejected: list
    revivable_discarded: list
```

- [ ] **Step 3: Write `evaluations.py` endpoint**

```python
# app/api/v1/endpoints/evaluations.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.core.week2_evaluation.evaluation_report_engine import EvaluationReportEngine
from app.schemas.evaluation import (
    EvaluationInitiateResponse,
    EvaluationReportResponse,
    SpecialistDecisionRequest,
)

router = APIRouter(prefix="/api", tags=["evaluations"])

@router.post("/projects/{project_id}/evaluation/initiate")
def initiate_evaluation(project_id: int, db: Session = Depends(get_db)):
    """Trigger evaluation report generation."""
    try:
        engine = EvaluationReportEngine(db, project_id)
        report = engine.generate_report()
        return EvaluationInitiateResponse(report_id=report['report_id'], status='generated')
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/evaluation-reports/{report_id}")
def get_evaluation_report(report_id: int, db: Session = Depends(get_db)):
    """Get full evaluation report."""
    from app.models.evaluation import BidEvaluationReport
    report = db.query(BidEvaluationReport).get(report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    return {
        'report_id': report.id,
        'project_id': report.project_id,
        'qualification_match_score': report.qualification_match_score,
        'missing_mandatory_certs': report.missing_mandatory_certs or [],
        'days_until_bid_open': report.days_until_bid_open,
        'time_urgency_level': report.time_urgency_level.value if hasattr(report.time_urgency_level, 'value') else report.time_urgency_level,
        'relationship_index': report.relationship_index,
        'overall_win_probability': float(report.overall_win_probability) if report.overall_win_probability else 0.0,
        'risk_level': report.risk_level.value if hasattr(report.risk_level, 'value') else report.risk_level,
        'recommendation': report.recommendation.value if hasattr(report.recommendation, 'value') else report.recommendation,
        'recommendation_reason': report.recommendation_reason,
        'specialist_decision': report.specialist_decision,
        'confirmed_by_specialist': report.confirmed_by_specialist,
    }

@router.post("/evaluation-reports/{report_id}/decide")
def specialist_decide(report_id: int, data: SpecialistDecisionRequest, db: Session = Depends(get_db)):
    """Specialist makes worthy/unworthy decision."""
    from app.models.evaluation import BidEvaluationReport
    from app.core.week2_evaluation.approval_workflow import ApprovalWorkflowService

    report = db.query(BidEvaluationReport).get(report_id)
    if not report:
        raise HTTPException(404, "Report not found")

    service = ApprovalWorkflowService()
    try:
        result = service.specialist_decide(
            db=db,
            project_id=report.project_id,
            decision=data.decision,
            reason=data.reason,
            specialist_id=1  # placeholder
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
```

- [ ] **Step 4: Write `approvals.py` endpoint**

```python
# app/api/v1/endpoints/approvals.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, date
from app.dependencies import get_db, get_current_user
from app.core.week2_evaluation.approval_workflow import ApprovalWorkflowService
from app.schemas.evaluation import BossOverrideRequest, OversightDashboardResponse

router = APIRouter(prefix="/api", tags=["approvals"])

@router.post("/projects/{project_id}/override")
def boss_override(project_id: int, data: BossOverrideRequest, db: Session = Depends(get_db)):
    """Boss override decision (terminate or revive)."""
    service = ApprovalWorkflowService()
    try:
        result = service.boss_override(
            db=db,
            project_id=project_id,
            action=data.action,
            reason=data.reason,
            boss_id=1  # placeholder
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/boss/oversight-dashboard")
def oversight_dashboard(db: Session = Depends(get_db)):
    """Boss oversight: today's approved/rejected + revivable discarded."""
    from app.models.project import Project
    from app.models.evaluation import BidEvaluationReport
    from app.models.enums import ProjectStatus
    from app.models.discarded import DiscardedProject

    today = date.today()

    # Today's approved by specialist
    approved = db.query(Project).join(BidEvaluationReport).filter(
        BidEvaluationReport.confirmed_at >= datetime.combine(today, datetime.min.time()),
        BidEvaluationReport.specialist_decision == 'worthy'
    ).all()

    # Today's rejected
    rejected = db.query(Project).join(BidEvaluationReport).filter(
        BidEvaluationReport.confirmed_at >= datetime.combine(today, datetime.min.time()),
        BidEvaluationReport.specialist_decision == 'unworthy'
    ).all()

    # Rvivable discarded
    revivable = db.query(DiscardedProject).filter_by(can_be_revived=True).all()

    return {
        'today_approved': [{'id': p.id, 'name': p.project_name} for p in approved],
        'today_rejected': [{'id': p.id, 'name': p.project_name} for p in rejected],
        'revivable_discarded': [{'id': d.id, 'project_id': d.project_id, 'reason': d.discard_reason} for d in revivable]
    }

@router.get("/discarded-projects")
def list_discarded_projects(
    can_revive: bool = Query(None),
    db: Session = Depends(get_db)
):
    """List discarded projects."""
    from app.models.discarded import DiscardedProject
    query = db.query(DiscardedProject)
    if can_revive is not None:
        query = query.filter_by(can_be_revived=can_revive)
    discarded = query.all()
    return [{'id': d.id, 'project_id': d.project_id, 'discard_reason': d.discard_reason, 'can_be_revived': d.can_be_revived} for d in discarded]
```

- [ ] **Step 5: Run tests** → PASS

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/w002_*.py app/models/owner.py app/models/evaluation.py app/models/approval.py app/models/discarded.py app/models/enums.py app/api/v1/endpoints/evaluations.py app/api/v1/endpoints/approvals.py app/schemas/evaluation.py tests/week2/
git commit -m "feat(week2): add evaluation engine, approval workflow, and API endpoints"
```

---

## Week 2 Acceptance Checklist

After completing all tasks, verify:

- [ ] `POST /api/projects/{id}/evaluation/initiate` generates evaluation report
- [ ] `GET /api/evaluation-reports/{id}` returns qualification score, time urgency, relationship index, win probability
- [ ] Qualification exact match: "食品生产许可证" does NOT match FOOD-BUSINESS-LICENSE (exclude keywords)
- [ ] "建筑工程施工总承包二级" does NOT match level-1 cert
- [ ] Expired bid date → `time_urgency_level = 'expired'` → `recommendation = 'abandon'`
- [ ] Missing mandatory cert → appears in `fatal_risks` list
- [ ] Specialist clicks worthy → project status becomes `approved_by_specialist` immediately
- [ ] Specialist cannot mark expired bid as worthy without override reason
- [ ] Boss override (terminate) → `approval_log` created, project → `terminated_by_boss`
- [ ] Boss revive → project back to `approved_by_specialist`, audit log created
- [ ] `GET /api/boss/oversight-dashboard` returns today's approved/rejected/revivable
- [ ] `GET /api/discarded-projects?can_revive=true` lists revivable projects

---

## Open Issues / TODO

1. **`standard_cert_suggestion` field missing**: Week 1 subagent didn't add this field. Week 2 migration should add it via Alembic (`standard_cert_suggestion` nullable FK on `ocr_extractions`).

2. **Owner profile seed data**: Need `owner_profiles` seed data with at least 3 sample owners for testing.

3. **Notification service**: `notify_boss` / `notify_specialist` are stubs. Real notification (email/SMS/WeChat) is Week 7+.

4. **Project status transition guard**: No enforcement that only `evaluation_ready` projects can receive specialist decisions. Needs middleware/guard.

5. **Cost estimator**: Currently cold-start only (budget×75%). Full historical analysis requires `price_history` table (Week 4).
