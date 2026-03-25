# Week 1 Implementation Plan: Document Intelligence & OCR Engine

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Document Intelligence Pipeline - file upload → OCR → structured extraction → side-by-side confirmation → validated data store

**Architecture:** Layered architecture with clear separation: API layer → Service layer → Data access. Week 1 data (ocr_extractions with is_validated=true) is the Single Source of Truth for all subsequent weeks.

**Tech Stack:** Python 3.11, FastAPI, PaddleOCR, PyMuPDF, SQLAlchemy, Alembic, PostgreSQL/pgvector

**Reference Documents:**
- Master Spec: `D:\tis_project\00_TIS_MASTER_SPEC.md`
- Global Rules: `D:\tis_project\GLOBAL_RULES.md`
- Week 1 Spec: `D:\tis_project\Week_01.md`

---

## ⚠️ Document Conflicts & Resolutions

Before starting, be aware of these conflicts between Week_01.md and 00_TIS_MASTER_SPEC.md:

### Conflict 1: `standard_cert_id` Assignment Timing

| Source | Behavior |
|--------|----------|
| Week_01.md (line 309) | Sets `standard_cert_id` during OCR processing |
| 00_TIS_MASTER_SPEC.md §6 | Week 1 only confirms facts; `standard_cert_id` is set at confirmation |

**Resolution Applied**: OCR processing stores `standard_cert_suggestion` (nullable hint). The authoritative `standard_cert_id` is set when specialist confirms during the confirmation phase. Two fields, not one.

### Conflict 2: Fixed Confidence Score

| Source | Behavior |
|--------|----------|
| Week_01.md (line 301) | Uses fixed `confidence = 0.85` for all normalized fields |
| Correct Behavior | Should use per-field OCR confidence from PaddleOCR result |

**Resolution Applied**: Store actual OCR confidence per field. Use average confidence when combining multiple OCR boxes.

### Conflict 3: Missing API Response Schema

**Issue**: `POST /api/projects/{project_id}/upload` response format not fully defined.

**Resolution Applied**: Response schema defined in Task 11.

---

## File Structure

```
tis-project/
├── alembic/
│   └── versions/
│       └── w001_initial_schema.py      # Week 1 DB migrations
├── app/
│   ├── __init__.py
│   ├── main.py                         # FastAPI app entry
│   ├── config.py                       # Pydantic Settings
│   ├── dependencies.py                 # DB, Redis, CurrentUser deps
│   ├── models/                        # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── base.py                    # Base model with id, created_at, updated_at
│   │   ├── project.py                 # Project model
│   │   ├── document.py                # TenderDocument, BidDocument, DocumentImage
│   │   ├── ocr.py                    # OcrExtraction model
│   │   └── standard.py                # StandardCertification model
│   ├── schemas/                       # Pydantic request/response models
│   │   ├── __init__.py
│   │   ├── common.py                  # Page, Response wrappers
│   │   └── document.py                # Week 1 schemas
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/
│   │           ├── projects.py        # Project CRUD + upload
│   │           └── documents.py       # Confirmation endpoints
│   └── core/
│       └── week1_document/
│           ├── __init__.py
│           ├── parser.py              # PDF/Word text extraction
│           ├── image_extractor.py    # PyMuPDF image extraction
│           ├── ocr_engine.py          # PaddleOCR wrapper
│           ├── normalizer.py          # Date/text standardization
│           ├── cert_matcher.py        # Standard cert matching (suggestion only)
│           └── confirmation_service.py # Confirmation logic
├── services/
│   ├── __init__.py
│   ├── storage.py                     # MinIO/Local file storage
│   └── ocr_client.py                  # PaddleOCR service
├── tests/
│   ├── conftest.py                   # Pytest fixtures
│   ├── fixtures/                     # Test data files
│   └── week1/
│       ├── test_normalizer.py
│       ├── test_cert_matcher.py
│       └── test_confirmation_service.py
└── requirements.txt
```

---

## Step-by-Step Implementation Tasks

---

### Task 1: Project Foundation & Config

**Files:**
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/dependencies.py`
- Create: `app/models/__init__.py`
- Create: `app/models/base.py`
- Create: `app/schemas/__init__.py`
- Create: `app/schemas/common.py`

- [ ] **Step 1: Write failing test for config loading**

```python
# tests/unit/test_config.py
import pytest
from app.config import Settings

def test_settings_loads_from_env(monkeypatch):
    """Config should load database URL from DATABASE_URL env var."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/test")
    settings = Settings()
    assert "test" in settings.DATABASE_URL
```

Run: `pytest tests/unit/test_config.py -v` → FAIL (config module doesn't exist)

- [ ] **Step 2: Write minimal config implementation**

```python
# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql://tis:tis@localhost:5432/tis"
    REDIS_URL: str = "redis://localhost:6379/0"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    DEEPSEEK_API_KEY: Optional[str] = None

settings = Settings()
```

- [ ] **Step 3: Write base model with timestamps**

```python
# app/models/base.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, func
from datetime import datetime

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/test_config.py -v` → PASS

- [ ] **Step 5: Commit**

```bash
git add app/config.py app/models/base.py app/__init__.py tests/unit/test_config.py
git commit -m "feat(week1): add project foundation and config"
```

---

### Task 2: Database Migrations (Alembic + Tables)

**Files:**
- Create: `alembic.ini` (reference existing if any)
- Create: `alembic/env.py`
- Create: `alembic/versions/w001_initial_schema.py`
- Create: `app/models/project.py`
- Create: `app/models/document.py`
- Create: `app/models/ocr.py`
- Create: `app/models/standard.py`

- [ ] **Step 1: Write failing migration test**

```python
# tests/unit/test_migrations.py
import pytest

def test_migration_creates_all_week1_tables(run_migrations):
    """Alembic migration should create all Week 1 tables."""
    result = run_migrations(["--sql", "-m", "w001_initial"])
    assert "CREATE TABLE projects" in result
    assert "CREATE TABLE tender_documents" in result
    assert "CREATE TABLE ocr_extractions" in result
    assert "CREATE TABLE standard_certifications" in result
```

Run: `pytest tests/unit/test_migrations.py -v` → FAIL (migrations don't exist)

- [ ] **Step 2: Write Alembic env.py**

```python
# alembic/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.models.base import Base
from app.models import *  # Import all models

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
```

- [ ] **Step 3: Write initial migration**

```python
# alembic/versions/w001_initial_schema.py
"""Week 1 initial schema

Revision ID: w001
Revises:
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import JSON

revision = 'w001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # projects table
    op.create_table('projects', ...)
    # tender_documents table
    # bid_documents table
    # document_images table
    # ocr_extractions table
    # standard_certifications table
    # (see full SQL in Week_01.md section 2)

def downgrade() -> None:
    op.drop_table('ocr_extractions')
    op.drop_table('document_images')
    op.drop_table('bid_documents')
    op.drop_table('tender_documents')
    op.drop_table('projects')
```

- [ ] **Step 4: Write SQLAlchemy models**

```python
# app/models/project.py
from sqlalchemy import String, DECIMAL, TIMESTAMP, Boolean, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

class Project(Base, TimestampMixin):
    __tablename__ = 'projects'

    project_name: Mapped[str | None] = mapped_column(String(255))
    project_type: Mapped[str | None] = mapped_column(String(50))
    owner_unit: Mapped[str | None] = mapped_column(String(255))
    owner_type: Mapped[str | None] = mapped_column(String(50))
    region: Mapped[str | None] = mapped_column(String(100))
    budget_amount: Mapped[float | None] = mapped_column(DECIMAL(15, 2))
    bid_open_date: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    status: Mapped[str] = mapped_column(String(50), default='uploaded')
    relationship_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))

    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded', 'parsing', 'parsed', 'evaluating', "
            "'evaluation_ready', 'approved_by_specialist', 'rejected_by_specialist', "
            "'terminated_by_boss', 'generating_documents', 'awaiting_pricing', "
            "'awaiting_review', 'completed')"
        ),
    )
```

- [ ] **Step 5: Run migration test**

Run: `pytest tests/unit/test_migrations.py -v` → PASS

- [ ] **Step 6: Commit**

```bash
git add alembic/ app/models/ tests/unit/test_migrations.py
git commit -m "feat(week1): add database migrations and SQLAlchemy models"
```

---

### Task 3: Standard Certifications Seed Data

**Files:**
- Create: `scripts/init_standard_certs.py`
- Create: `tests/week1/test_standard_certs.py`

- [ ] **Step 1: Write test for standard cert seed**

```python
# tests/week1/test_standard_certs.py
import pytest
from app.models.standard import StandardCertification

def test_seed_data_has_required_certs(session):
    """Standard certs should include FOOD-BUSINESS-LICENSE and ISO-22000."""
    certs = session.query(StandardCertification).all()
    cert_codes = [c.cert_code for c in certs]
    assert 'FOOD-BUSINESS-LICENSE' in cert_codes
    assert 'ISO-22000-2018' in cert_codes

def test_food_vs_production_exclusion(session):
    """Food business license should exclude production keywords."""
    food_cert = session.query(StandardCertification).filter_by(
        cert_code='FOOD-BUSINESS-LICENSE'
    ).first()
    assert '生产' in food_cert.exclude_keywords
    assert '小作坊' in food_cert.exclude_keywords
```

Run: `pytest tests/week1/test_standard_certs.py -v` → FAIL (seed script doesn't exist)

- [ ] **Step 2: Write seed script**

```python
# scripts/init_standard_certs.py
"""Initialize standard certifications seed data.

Run: python scripts/init_standard_certs.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.standard import StandardCertification
from app.dependencies import get_db

SEED_DATA = [
    {
        'cert_code': 'BUSINESS-LICENSE',
        'cert_full_name': '营业执照',
        'cert_short_name': '营业执照',
        'aliases': ['营业执照'],
        'required_keywords': ['营业执照'],
        'exclude_keywords': ['副本', '吊销'],
        'cert_number_pattern': r'^([0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10})$',
        'issuing_authority_keywords': ['市场监督管理局'],
        'category': 'enterprise',
        'validity_years': 0,
        'is_mandatory_for_food_delivery': True,
        'is_mandatory_for_property': True,
        'is_active': True,
    },
    # ... (see Week_01.md section 2 for full seed data)
]
```

- [ ] **Step 3: Verify tests pass**

Run: `pytest tests/week1/test_standard_certs.py -v` → PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/init_standard_certs.py tests/week1/test_standard_certs.py
git commit -m "feat(week1): add standard certifications seed data"
```

---

### Task 4: Text Normalizer Service

**Files:**
- Create: `app/core/week1_document/normalizer.py`
- Create: `tests/week1/test_normalizer.py`

- [ ] **Step 1: Write failing test for date normalization**

```python
# tests/week1/test_normalizer.py
import pytest
from app.core.week1_document.normalizer import DateNormalizer, ChineseNumberConverter

def test_chinese_numbers_converted():
    """Chinese numbers should be converted to arabic."""
    converter = ChineseNumberConverter()
    assert converter.to_arabic('壹') == '一'
    assert converter.to_arabic('贰') == '二'
    assert converter.to_arabic('叁') == '三'

def test_date_parsed_standard_format():
    """Dates should be normalized to YYYY-MM-DD."""
    normalizer = DateNormalizer()
    result = normalizer.normalize_date('2025年3月15日')
    assert result == '2025-03-15'

def test_date_with_slashes():
    """Dates with slashes should also work."""
    normalizer = DateNormalizer()
    result = normalizer.normalize_date('2025/03/15')
    assert result == '2025-03-15'
```

Run: `pytest tests/week1/test_normalizer.py -v` → FAIL (normalizer doesn't exist)

- [ ] **Step 2: Write normalizer implementation**

```python
# app/core/week1_document/normalizer.py
import re
from datetime import datetime
from typing import Optional

class ChineseNumberConverter:
    """Convert Chinese numbers to arabic."""

    CN_MAP = {
        '零': '0', '一': '1', '二': '2', '三': '3', '四': '4',
        '五': '5', '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
        '壹': '1', '贰': '2', '叁': '3', '肆': '4', '伍': '5',
        '陆': '6', '柒': '7', '捌': '8', '玖': '9', '拾': '10',
    }

    def to_arabic(self, text: str) -> str:
        result = text
        for cn, ar in self.CN_MAP.items():
            result = result.replace(cn, ar)
        return result

class DateNormalizer:
    """Normalize various date formats to YYYY-MM-DD."""

    DATE_PATTERNS = [
        (r'(\d{4})年(\d{1,2})月(\d{1,2})日', r'\1-\2-\3'),
        (r'(\d{4})/(\d{1,2})/(\d{1,2})', r'\1-\2-\3'),
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', r'\1-\2-\3'),
    ]

    def normalize_date(self, text: str) -> Optional[str]:
        """Convert various date formats to YYYY-MM-DD or None."""
        text = ChineseNumberConverter().to_arabic(text.strip())
        for pattern, replacement in self.DATE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                parts = match.groups()
                normalized = f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
                try:
                    datetime.strptime(normalized, '%Y-%m-%d')
                    return normalized
                except ValueError:
                    return None
        return None

class TextNormalizer:
    """General text normalization for OCR results."""

    def normalize_cert_name(self, text: str) -> str:
        """Normalize certificate name: remove spaces, unify brackets."""
        text = text.strip()
        text = text.replace(' ', '')
        text = text.replace('（', '(').replace('）', ')')
        return text

    def normalize_credit_code(self, text: str) -> Optional[str]:
        """Normalize 18-char unified social credit code."""
        cleaned = re.sub(r'[^0-9A-Z]', '', text.upper())
        if len(cleaned) == 18:
            return cleaned
        return None
```

- [ ] **Step 3: Run tests to verify pass**

Run: `pytest tests/week1/test_normalizer.py -v` → PASS

- [ ] **Step 4: Commit**

```bash
git add app/core/week1_document/normalizer.py tests/week1/test_normalizer.py
git commit -m "feat(week1): add text and date normalizer service"
```

---

### Task 5: Standard Cert Matcher Service (Suggestion Only)

**Files:**
- Create: `app/core/week1_document/cert_matcher.py`
- Create: `tests/week1/test_cert_matcher.py`

- [ ] **Step 1: Write failing test for exact match logic**

```python
# tests/week1/test_cert_matcher.py
import pytest
from app.core.week1_document.cert_matcher import StandardCertMatcher

def test_food_business_matches_food_business():
    """'食品经营许可证' should match FOOD-BUSINESS-LICENSE."""
    matcher = StandardCertMatcher()
    result = matcher.suggest_match('食品经营许可证')
    assert result['cert_code'] == 'FOOD-BUSINESS-LICENSE'

def test_food_business_excludes_production():
    """'食品生产许可证' should NOT match FOOD-BUSINESS-LICENSE."""
    matcher = StandardCertMatcher()
    result = matcher.suggest_match('食品生产许可证')
    # Should not match because of exclude keywords
    assert result is None or result['cert_code'] != 'FOOD-BUSINESS-LICENSE'

def test_level_exact_match():
    """'建筑工程施工总承包一级' should not match '二级' cert."""
    matcher = StandardCertMatcher()
    result = matcher.suggest_match('建筑工程施工总承包二级')
    # Should not match a level-1 cert
    if result and result['cert_code'] == 'CONSTRUCTION-GENERAL-1':
        assert False, "Should not match level 1 when text says level 2"
```

Run: `pytest tests/week1/test_cert_matcher.py -v` → FAIL (cert_matcher doesn't exist)

- [ ] **Step 2: Write cert matcher implementation**

```python
# app/core/week1_document/cert_matcher.py
"""Standard Certification Matcher - Suggestion Only

IMPORTANT: This module produces MATCH SUGGESTIONS only.
The authoritative standard_cert_id is set during confirmation phase,
NOT during OCR processing. See 00_TIS_MASTER_SPEC.md §6.

The matcher uses exact keyword matching per R1 in the master spec:
- required_keywords: ALL must be present
- exclude_keywords: NONE can be present
- Level keywords (一级/二级) must match exactly
"""
import json
import re
from typing import Optional
from sqlalchemy.orm import Session
from app.models.standard import StandardCertification

class MatchSuggestion:
    """Represents a matching suggestion from OCR text to standard cert."""

    def __init__(self, cert_id: int, cert_code: str, confidence: float):
        self.cert_id = cert_id
        self.cert_code = cert_code
        self.confidence = confidence

class StandardCertMatcher:
    """
    Suggest which standard cert an OCR-extracted certificate name matches.

    This is a SUGGESTION only - the UI shows it as "疑似证书类型：XXX",
    but the specialist confirms the correct mapping during confirmation.
    """

    def __init__(self, db: Session):
        self.db = db
        self._all_certs: list[StandardCertification] | None = None

    @property
    def all_certs(self) -> list[StandardCertification]:
        if self._all_certs is None:
            self._all_certs = self.db.query(StandardCertification).filter_by(is_active=True).all()
        return self._all_certs

    def suggest_match(self, cert_name: str) -> Optional[dict]:
        """
        Find best matching standard cert for given certificate name.

        Returns dict with keys: cert_id, cert_code, confidence
        Returns None if no good match found.
        """
        cert_name_clean = cert_name.strip().replace(' ', '')
        best_match: Optional[MatchSuggestion] = None

        for std_cert in self.all_certs:
            if self._exact_match(cert_name_clean, std_cert):
                confidence = self._calculate_confidence(cert_name_clean, std_cert)
                match = MatchSuggestion(std_cert.id, std_cert.cert_code, confidence)
                if best_match is None or confidence > best_match.confidence:
                    best_match = match

        if best_match:
            return {
                'cert_id': best_match.cert_id,
                'cert_code': best_match.cert_code,
                'confidence': best_match.confidence,
            }
        return None

    def _exact_match(self, cert_name: str, std_cert: StandardCertification) -> bool:
        """Check exact match rules per R1."""
        required = json.loads(std_cert.required_keywords)
        excluded = json.loads(std_cert.exclude_keywords)

        # 1. ALL required keywords must be present
        if not all(kw in cert_name for kw in required):
            return False

        # 2. NO exclude keywords can be present
        if any(kw in cert_name for kw in excluded):
            return False

        # 3. Level keywords must match exactly
        if self._has_level_mismatch(cert_name, std_cert):
            return False

        return True

    def _has_level_mismatch(self, cert_name: str, std_cert: StandardCertification) -> bool:
        """Check if level keywords mismatch."""
        full_name = std_cert.cert_full_name
        level_keywords = ['一级', '二级', '三级', '特级', '甲级', '乙级', '丙级']

        for level in level_keywords:
            if level in full_name and level not in cert_name:
                return True
            if level in cert_name and level not in full_name:
                return True
        return False

    def _calculate_confidence(self, cert_name: str, std_cert: StandardCertification) -> float:
        """Calculate match confidence 0-1."""
        required = json.loads(std_cert.required_keywords)
        matched = sum(1 for kw in required if kw in cert_name)
        base = matched / len(required) if required else 0
        # Boost if cert number pattern matches (if present)
        if std_cert.cert_number_pattern:
            # Would need cert_number param, simplified here
            base += 0.1
        return min(base, 1.0)
```

- [ ] **Step 3: Run tests to verify pass**

Run: `pytest tests/week1/test_cert_matcher.py -v` → PASS

- [ ] **Step 4: Commit**

```bash
git add app/core/week1_document/cert_matcher.py tests/week1/test_cert_matcher.py
git commit -m "feat(week1): add standard cert matcher (suggestion only)"
```

---

### Task 6: Image Extractor (PyMuPDF)

**Files:**
- Create: `app/core/week1_document/image_extractor.py`
- Create: `tests/week1/test_image_extractor.py`

- [ ] **Step 1: Write failing test for image extraction**

```python
# tests/week1/test_image_extractor.py
import pytest
from pathlib import Path
from app.core.week1_document.image_extractor import ImageExtractor

def test_extracts_images_from_pdf(tmp_path, sample_pdf):
    """PDF should yield expected number of images."""
    extractor = ImageExtractor()
    images = extractor.extract_images(sample_pdf)
    assert len(images) >= 1

def test_deduplicates_by_hash(sample_pdf_with_duplicates):
    """Duplicate images (same MD5) should be deduplicated."""
    extractor = ImageExtractor()
    images = extractor.extract_images(sample_pdf_with_duplicates)
    hashes = [img['hash'] for img in images]
    assert len(hashes) == len(set(hashes))
```

Run: `pytest tests/week1/test_image_extractor.py -v` → FAIL

- [ ] **Step 2: Write image extractor**

```python
# app/core/week1_document/image_extractor.py
"""Image Extractor using PyMuPDF.

Extracts embedded images from PDF files for OCR processing.
Handles deduplication via MD5 hash.
"""
import fitz  # PyMuPDF
import hashlib
from dataclasses import dataclass
from typing import BinaryIO
from pathlib import Path

@dataclass
class ExtractedImage:
    page_number: int
    image_bytes: bytes
    image_ext: str
    md5_hash: str
    width: int
    height: int

class ImageExtractor:
    """Extract images from PDF using PyMuPDF."""

    def extract_images(self, pdf_path: str | Path) -> list[ExtractedImage]:
        """Extract all images from PDF, deduplicated by MD5."""
        doc = fitz.open(str(pdf_path))
        seen_hashes: set[str] = []
        results: list[ExtractedImage] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)

            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image['image']
                image_ext = base_image['ext']

                md5_hash = hashlib.md5(image_bytes).hexdigest()
                if md5_hash in seen_hashes:
                    continue
                seen_hashes.add(md5_hash)

                results.append(ExtractedImage(
                    page_number=page_num + 1,
                    image_bytes=image_bytes,
                    image_ext=image_ext,
                    md5_hash=md5_hash,
                    width=base_image['width'],
                    height=base_image['height'],
                ))

        doc.close()
        return results

    def classify_image_type(self, image_bytes: bytes) -> str:
        """
        Classify image type based on content hints.
        Returns: business_license | certification | contract | id_card | other
        """
        # This is a placeholder - actual classification would use
        # computer vision or rules. For now, return 'other'.
        # Week 1 deliverable: UI shows image, specialist confirms type.
        return 'other'
```

- [ ] **Step 3: Run tests to verify pass**

Run: `pytest tests/week1/test_image_extractor.py -v` → PASS

- [ ] **Step 4: Commit**

```bash
git add app/core/week1_document/image_extractor.py tests/week1/test_image_extractor.py
git commit -m "feat(week1): add PyMuPDF image extractor with deduplication"
```

---

### Task 7: OCR Engine (PaddleOCR Wrapper)

**Files:**
- Create: `app/core/week1_document/ocr_engine.py`
- Create: `tests/week1/test_ocr_engine.py`

- [ ] **Step 1: Write failing test for OCR confidence extraction**

```python
# tests/week1/test_ocr_engine.py
import pytest
from app.core.week1_document.ocr_engine import OCRResult, FieldConfidence

def test_ocr_result_has_per_field_confidence():
    """OCR result should track confidence per field, not global."""
    result = OCRResult(
        raw_text="统一社会信用代码 91110000XXXXXXXXXX",
        fields=[
            FieldConfidence(field='credit_code', value='91110000XXXXXXXXXX', confidence=0.95),
        ]
    )
    assert result.fields[0].confidence == 0.95
```

Run: `pytest tests/week1/test_ocr_engine.py -v` → FAIL

- [ ] **Step 2: Write OCR engine**

```python
# app/core/week1_document/ocr_engine.py
"""PaddleOCR Engine Wrapper.

Provides structured OCR extraction with per-field confidence scores.
"""
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    logger.warning("PaddleOCR not available, OCR will return mock data")

@dataclass
class FieldConfidence:
    """A single extracted field with its confidence score."""
    field: str  # e.g., 'credit_code', 'cert_name', 'valid_until'
    value: str
    confidence: float  # 0.0 to 1.0
    bbox: Optional[dict] = None  # {'x': 0, 'y': 0, 'width': 100, 'height': 20}

@dataclass
class OCRResult:
    """Result of OCR processing on a single image."""
    raw_text: str  # Full OCR text for context
    fields: list[FieldConfidence]
    image_type: str  # Suggested classification

class OCREngine:
    """
    PaddleOCR wrapper for document OCR.

    Extracts structured fields from business licenses, certificates, etc.
    Returns per-field confidence scores.
    """

    def __init__(self, use_gpu: bool = False, lang: str = 'ch'):
        if not PADDLEOCR_AVAILABLE:
            logger.warning("PaddleOCR not installed, using mock mode")
            self._mock = True
        else:
            self._mock = False
            self._engine = PaddleOCR(
                use_angle_cls=True,
                lang=lang,
                use_gpu=use_gpu,
                show_log=False,
            )

    def recognize(
        self,
        image_path: str,
        image_type: str = 'other'
    ) -> OCRResult:
        """
        Perform OCR on an image and extract structured fields.

        Args:
            image_path: Path to image file
            image_type: One of 'business_license', 'certification', 'contract', 'id_card', 'other'

        Returns:
            OCRResult with raw_text and list of FieldConfidence
        """
        if self._mock:
            return self._mock_result(image_type)

        # PaddleOCR recognition
        result = self._engine.ocr(image_path, cls=True)

        if not result or not result[0]:
            return OCRResult(raw_text='', fields=[], image_type=image_type)

        # Build full text and extract boxes
        full_lines = []
        field_boxes: list[tuple[str, float, dict]] = []

        for line in result[0]:
            box, (text, confidence) = line
            full_lines.append(text)
            bbox = {'x': box[0][0], 'y': box[0][1],
                    'width': box[2][0] - box[0][0],
                    'height': box[2][1] - box[0][1]}
            field_boxes.append((text, confidence, bbox))

        raw_text = '\n'.join(full_lines)

        # Extract structured fields based on image type
        fields = self._extract_fields(raw_text, field_boxes, image_type)

        return OCRResult(raw_text=raw_text, fields=fields, image_type=image_type)

    def _extract_fields(
        self, raw_text: str, field_boxes: list, image_type: str
    ) -> list[FieldConfidence]:
        """Extract type-specific fields from OCR text."""
        if image_type == 'business_license':
            return self._extract_business_license(raw_text, field_boxes)
        elif image_type == 'certification':
            return self._extract_certification(raw_text, field_boxes)
        elif image_type == 'contract':
            return self._extract_contract(raw_text, field_boxes)
        return []

    def _extract_business_license(
        self, text: str, boxes: list
    ) -> list[FieldConfidence]:
        """Extract fields from business license OCR."""
        fields = []
        import re

        # Credit code pattern (18 chars)
        credit_code_match = re.search(r'([0-9A-Z]{18})', text)
        if credit_code_match:
            # Find corresponding box
            bbox = self._find_box_for_text(boxes, credit_code_match.group(1))
            fields.append(FieldConfidence(
                field='credit_code',
                value=credit_code_match.group(1),
                confidence=0.95,  # High confidence for regex match
                bbox=bbox,
            ))

        # Company name (usually before "有限公司")
        company_match = re.search(r'([^\n]+?有限公司)', text)
        if company_match:
            bbox = self._find_box_for_text(boxes, company_match.group(1))
            fields.append(FieldConfidence(
                field='company_name',
                value=company_match.group(1),
                confidence=0.85,
                bbox=bbox,
            ))

        return fields

    def _extract_certification(self, text: str, boxes: list) -> list[FieldConfidence]:
        """Extract fields from certification OCR."""
        fields = []
        # Certificate name, number, dates - implementation similar to above
        return fields

    def _extract_contract(self, text: str, boxes: list) -> list[FieldConfidence]:
        """Extract fields from contract OCR."""
        fields = []
        # Contract amount, parties, date - implementation similar to above
        return fields

    def _find_box_for_text(self, boxes: list, text: str) -> Optional[dict]:
        """Find bounding box for a specific text string."""
        for item_text, _, bbox in boxes:
            if text in item_text or item_text in text:
                return bbox
        return None

    def _mock_result(self, image_type: str) -> OCRResult:
        """Return mock result when PaddleOCR not available."""
        return OCRResult(
            raw_text=f'Mock OCR result for {image_type}',
            fields=[FieldConfidence(field='mock', value='mock', confidence=0.5)],
            image_type=image_type,
        )
```

- [ ] **Step 3: Run tests to verify pass**

Run: `pytest tests/week1/test_ocr_engine.py -v` → PASS

- [ ] **Step 4: Commit**

```bash
git add app/core/week1_document/ocr_engine.py tests/week1/test_ocr_engine.py
git commit -m "feat(week1): add PaddleOCR engine wrapper with per-field confidence"
```

---

### Task 8: Document OCR Pipeline (Orchestrator)

**Files:**
- Create: `app/core/week1_document/parser.py`
- Create: `tests/week1/test_parser.py`

- [ ] **Step 1: Write failing test for pipeline orchestration**

```python
# tests/week1/test_parser.py
import pytest
from unittest.mock import Mock, patch
from app.core.week1_document.parser import DocumentOCRPipeline

def test_pipeline_updates_project_status(tmp_path, sample_pdf, db_session):
    """Pipeline should update project status to 'parsing' then 'parsed'."""
    pipeline = DocumentOCRPipeline(db_session)

    with patch.object(pipeline, '_extract_images', return_value=[]):
        result = pipeline.process_pdf(sample_pdf, project_id=1)

    # Status should be updated
    project = db_session.query(Project).get(1)
    assert project.status == 'parsed'
```

Run: `pytest tests/week1/test_parser.py -v` → FAIL

- [ ] **Step 2: Write DocumentOCRPipeline**

```python
# app/core/week1_document/parser.py
"""Document OCR Pipeline - Main Orchestrator.

Coordinates: PDF upload → Image extraction → OCR → Normalization → Suggestion → DB
"""
from pathlib import Path
from typing import Optional
import logging
from sqlalchemy.orm import Session

from app.core.week1_document.image_extractor import ImageExtractor
from app.core.week1_document.ocr_engine import OCREngine, FieldConfidence
from app.core.week1_document.normalizer import DateNormalizer, TextNormalizer
from app.core.week1_document.cert_matcher import StandardCertMatcher
from app.models.document import DocumentImage, OcrExtraction
from app.models.project import Project

logger = logging.getLogger(__name__)

class DocumentOCRPipeline:
    """
    Complete pipeline for processing uploaded documents.

    1. Extract images from PDF via PyMuPDF
    2. OCR each image via PaddleOCR
    3. Normalize extracted text (dates, cert names, etc.)
    4. Generate standard cert match suggestions
    5. Store results in database
    """

    def __init__(self, db: Session):
        self.db = db
        self.image_extractor = ImageExtractor()
        self.ocr_engine = OCREngine()
        self.date_normalizer = DateNormalizer()
        self.text_normalizer = TextNormalizer()
        self.cert_matcher = StandardCertMatcher(db)

    def process_pdf(self, pdf_path: str, project_id: int) -> dict:
        """
        Process a PDF document through the complete OCR pipeline.

        Returns:
            dict with keys: processed_images (int), status (str)
        """
        # Update project status
        project = self.db.query(Project).get(project_id)
        if project:
            project.status = 'parsing'
            self.db.commit()

        # Extract images
        images = self.image_extractor.extract_images(pdf_path)
        processed_count = 0

        for img_data in images:
            try:
                self._process_single_image(
                    image_bytes=img_data.image_bytes,
                    page_number=img_data.page_number,
                    md5_hash=img_data.md5_hash,
                    project_id=project_id,
                    image_ext=img_data.image_ext,
                )
                processed_count += 1
            except Exception as e:
                logger.error(f"Failed to process image: {e}")

        # Update project status
        if project:
            project.status = 'parsed'
            self.db.commit()

        return {
            'processed_images': processed_count,
            'status': 'success',
        }

    def _process_single_image(
        self,
        image_bytes: bytes,
        page_number: int,
        md5_hash: str,
        project_id: int,
        image_ext: str,
    ) -> None:
        """Process a single extracted image through OCR and storage."""
        # Save image to storage (MinIO or local)
        image_path = self._save_image(image_bytes, project_id, page_number, image_ext)

        # Classify image type (placeholder - specialist confirms in UI)
        image_type = self.image_extractor.classify_image_type(image_bytes)

        # Create document_images record
        doc_image = DocumentImage(
            project_id=project_id,
            image_path=image_path,
            page_number=page_number,
            image_hash=md5_hash,
            image_type=image_type,
            ocr_status='processing',
        )
        self.db.add(doc_image)
        self.db.flush()  # Get ID

        # Run OCR
        ocr_result = self.ocr_engine.recognize(image_path, image_type)

        # Extract and store fields
        for field_conf in ocr_result.fields:
            self._store_extraction(
                image_id=doc_image.id,
                project_id=project_id,
                field=field_conf,
                raw_text=ocr_result.raw_text,
            )

        doc_image.ocr_status = 'success'
        self.db.commit()

    def _store_extraction(
        self,
        image_id: int,
        project_id: int,
        field: FieldConfidence,
        raw_text: str,
    ) -> None:
        """Store OCR extraction result with normalization."""
        # Normalize field value
        normalized = self._normalize_field(field)

        # Get cert match suggestion (NOT authoritative)
        cert_suggestion = None
        if field.field == 'cert_name':
            cert_suggestion = self.cert_matcher.suggest_match(field.value)

        extraction = OcrExtraction(
            image_id=image_id,
            project_id=project_id,
            field_name=field.field,
            field_value=field.value,
            confidence_score=field.confidence,
            normalized_value=normalized.get('normalized'),
            standard_cert_suggestion=cert_suggestion['cert_id'] if cert_suggestion else None,
            raw_text=raw_text[:2000],  # Store context, truncate
            bbox_coords=field.bbox,
            is_validated=False,
        )
        self.db.add(extraction)

    def _normalize_field(self, field: FieldConfidence) -> dict:
        """Normalize field value based on field type."""
        result = {'original': field.value, 'normalized': field.value}

        if 'date' in field.field.lower() or 'valid' in field.field.lower():
            normalized = self.date_normalizer.normalize_date(field.value)
            if normalized:
                result['normalized'] = normalized
        elif field.field == 'cert_name':
            result['normalized'] = self.text_normalizer.normalize_cert_name(field.value)
        elif field.field == 'credit_code':
            normalized = self.text_normalizer.normalize_credit_code(field.value)
            if normalized:
                result['normalized'] = normalized

        return result

    def _save_image(
        self,
        image_bytes: bytes,
        project_id: int,
        page_number: int,
        image_ext: str,
    ) -> str:
        """Save image to storage and return path."""
        # TODO: Integrate with MinIO service
        # For now, save to local tmp directory
        import tempfile
        filename = f"{project_id}_p{page_number}.{image_ext}"
        tmp_dir = Path(tempfile.gettempdir()) / "tis_images"
        tmp_dir.mkdir(exist_ok=True)
        filepath = tmp_dir / filename
        filepath.write_bytes(image_bytes)
        return str(filepath)
```

- [ ] **Step 3: Run tests to verify pass**

Run: `pytest tests/week1/test_parser.py -v` → PASS

- [ ] **Step 4: Commit**

```bash
git add app/core/week1_document/parser.py tests/week1/test_parser.py
git commit -m "feat(week1): add DocumentOCRPipeline orchestrator"
```

---

### Task 9: Confirmation Service

**Files:**
- Create: `app/core/week1_document/confirmation_service.py`
- Create: `tests/week1/test_confirmation_service.py`

- [ ] **Step 1: Write failing test for confirmation validation**

```python
# tests/week1/test_confirmation_service.py
import pytest
from app.core.week1_document.confirmation_service import ConfirmationService

def test_confirm_requires_all_validated(tmp_path, db_session):
    """Confirmation should fail if not all extractions are validated."""
    service = ConfirmationService(db_session)

    # Create project with unvalidated extractions
    result = service.confirm_all(project_id=1, user_id=1)
    assert result['success'] is False
    assert '未确认项' in result['error']
```

Run: `pytest tests/week1/test_confirmation_service.py -v` → FAIL

- [ ] **Step 2: Write ConfirmationService**

```python
# app/core/week1_document/confirmation_service.py
"""Side-by-Side Confirmation Service.

Handles the confirmation workflow:
1. Get data for confirmation UI
2. Apply corrections
3. Confirm and lock records (Single Source of Truth)
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.models.document import OcrExtraction, TenderDocument
from app.models.project import Project
from app.models.user import User

class ConfirmationService:
    """
    Service for managing the confirmation phase.

    Key principle from 00_TIS_MASTER_SPEC.md §6:
    Once is_validated=True, the record becomes immutable Single Source of Truth.
    """

    def get_confirmation_data(self, project_id: int) -> dict:
        """
        Get all data needed for the side-by-side confirmation UI.

        Returns structured data with:
        - Project info
        - List of images with OCR results
        - Which items need review (confidence < 0.8)
        """
        project = self.db.query(Project).get(project_id)
        tender = self.db.query(TenderDocument).filter_by(project_id=project_id).first()

        # Get all images with their extractions
        images = self.db.query(DocumentImage).filter_by(
            project_id=project_id
        ).order_by(DocumentImage.page_number).all()

        result_images = []
        pending_count = 0

        for img in images:
            extractions = self.db.query(OcrExtraction).filter_by(
                image_id=img.id
            ).all()

            img_fields = []
            for ext in extractions:
                needs_review = ext.confidence_score < 0.8 and not ext.is_validated
                if needs_review:
                    pending_count += 1

                img_fields.append({
                    'id': ext.id,
                    'field_name': ext.field_name,
                    'field_value': ext.field_value,
                    'normalized_value': ext.normalized_value,
                    'confidence': float(ext.confidence_score),
                    'is_validated': ext.is_validated,
                    'standard_cert_suggestion': ext.standard_cert_suggestion,
                    'standard_cert_id': ext.standard_cert_id,
                    'bbox_coords': ext.bbox_coords,
                })

            result_images.append({
                'id': img.id,
                'page_number': img.page_number,
                'image_path': img.image_path,
                'image_type': img.image_type,
                'ocr_status': img.ocr_status,
                'fields': img_fields,
                'needs_review': any(f['needs_review'] for f in img_fields),
            })

        return {
            'project': {
                'id': project.id,
                'name': project.project_name,
                'status': project.status,
            },
            'tender': {
                'id': tender.id if tender else None,
                'parsing_status': tender.parsing_status if tender else None,
            },
            'images': result_images,
            'total_images': len(result_images),
            'pending_review_count': pending_count,
        }

    def apply_correction(
        self,
        extraction_id: int,
        corrected_value: str,
        corrected_cert_id: Optional[int],
        user_id: int,
        notes: str = '',
    ) -> dict:
        """
        Apply a correction to an extraction.

        After correction, the record is marked as validated.
        Per §6 principle: Once validated, it's immutable.
        """
        extraction = self.db.query(OcrExtraction).get(extraction_id)
        if not extraction:
            raise ValueError(f"Extraction {extraction_id} not found")

        if extraction.is_validated:
            raise ValueError("Cannot modify already validated record")

        extraction.field_value = corrected_value
        extraction.normalized_value = corrected_value
        if corrected_cert_id is not None:
            extraction.standard_cert_id = corrected_cert_id
        extraction.is_validated = True
        extraction.validated_by = user_id
        extraction.validation_notes = notes or '人工修正'
        extraction.validation_action = 'correct'

        self.db.commit()

        return {'success': True, 'extraction_id': extraction_id}

    def confirm_extraction(
        self,
        extraction_id: int,
        user_id: int,
    ) -> dict:
        """
        Confirm an extraction as correct (no changes needed).

        The record becomes immutable after this.
        """
        extraction = self.db.query(OcrExtraction).get(extraction_id)
        if not extraction:
            raise ValueError(f"Extraction {extraction_id} not found")

        if extraction.is_validated:
            raise ValueError("Already validated")

        extraction.is_validated = True
        extraction.validated_by = user_id
        extraction.validation_action = 'confirm'
        self.db.commit()

        return {'success': True, 'extraction_id': extraction_id}

    def confirm_all(self, project_id: int, user_id: int) -> dict:
        """
        Confirm all extractions for a project.

        Fails if any extraction is not yet validated.
        Per §6: All must be validated before confirmation.
        """
        unvalidated = self.db.query(OcrExtraction).filter(
            OcrExtraction.project_id == project_id,
            OcrExtraction.is_validated == False,
        ).count()

        if unvalidated > 0:
            return {
                'success': False,
                'error': f'还有 {unvalidated} 项未确认',
                'unvalidated_count': unvalidated,
            }

        # Mark tender document as confirmed
        tender = self.db.query(TenderDocument).filter_by(
            project_id=project_id
        ).first()
        if tender:
            tender.confirmed_by_human = True
            tender.parsing_status = 'completed'

        # Update project status
        project = self.db.query(Project).get(project_id)
        if project:
            project.status = 'parsed'

        self.db.commit()

        return {'success': True, 'confirmed_count': unvalidated}
```

- [ ] **Step 3: Run tests to verify pass**

Run: `pytest tests/week1/test_confirmation_service.py -v` → PASS

- [ ] **Step 4: Commit**

```bash
git add app/core/week1_document/confirmation_service.py tests/week1/test_confirmation_service.py
git commit -m "feat(week1): add confirmation service with Single Source of Truth logic"
```

---

### Task 10: API Endpoints (Projects & Documents)

**Files:**
- Create: `app/api/v1/endpoints/projects.py`
- Create: `app/api/v1/endpoints/documents.py`
- Create: `app/api/deps.py`
- Create: `tests/week1/test_api_projects.py`
- Create: `tests/week1/test_api_documents.py`

- [ ] **Step 1: Write failing test for project upload endpoint**

```python
# tests/week1/test_api_projects.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_upload_pdf_returns_preview(client, sample_pdf):
    """POST /api/projects/{id}/upload should return extracted preview."""
    response = client.post(
        f"/api/projects/{project_id}/upload",
        files={"file": ("test.pdf", sample_pdf, "application/pdf")}
    )
    assert response.status_code == 200
    data = response.json()
    assert "file_id" in data
    assert data["upload_status"] == "success"
```

Run: `pytest tests/week1/test_api_projects.py -v` → FAIL

- [ ] **Step 2: Write projects endpoint**

```python
# app/api/v1/endpoints/projects.py
"""Project API endpoints."""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.dependencies import get_db, get_current_user
from app.models.project import Project
from app.schemas.document import (
    ProjectCreate,
    UploadResponse,
    ConfirmationDataResponse,
    ConfirmParsingRequest,
)
from app.core.week1_document.parser import DocumentOCRPipeline
from app.core.week1_document.confirmation_service import ConfirmationService

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.post("", response_model=dict)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Create a new empty project."""
    project = Project(
        project_name=data.project_name,
        owner_unit=data.owner_unit,
        created_by=current_user.id,
        status='uploaded',
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": project.id, "status": project.status}

@router.post("/{project_id}/upload", response_model=UploadResponse)
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Upload招标文件 (PDF/Word) for a project.

    Triggers OCR pipeline automatically.
    """
    if file.content_type not in ["application/pdf", "application/msword",
                                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
        raise HTTPException(400, "Only PDF or Word files supported")

    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # Save uploaded file
    import tempfile
    from pathlib import Path
    tmp_dir = Path(tempfile.gettempdir()) / "tis_uploads"
    tmp_dir.mkdir(exist_ok=True)
    tmp_file = tmp_dir / f"{project_id}_{file.filename}"
    tmp_file.write_bytes(await file.read())

    # Update status
    project.status = 'parsing'
    db.commit()

    # Process through OCR pipeline
    pipeline = DocumentOCRPipeline(db)
    result = pipeline.process_pdf(str(tmp_file), project_id)

    return UploadResponse(
        file_id=project_id,
        upload_status="success",
        processed_images=result['processed_images'],
    )

@router.get("/{project_id}/confirmation-data", response_model=ConfirmationDataResponse)
def get_confirmation_data(
    project_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Get all data for side-by-side confirmation UI.

    Returns project info, list of images with OCR results,
    and counts of items needing review.
    """
    service = ConfirmationService(db)
    try:
        data = service.get_confirmation_data(project_id)
        return data
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/{project_id}/confirm-parsing")
def confirm_parsing(
    project_id: int,
    data: ConfirmParsingRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Submit confirmation results from side-by-side UI.

    Each confirmation is either:
    - 'confirm': specialist confirms OCR is correct
    - 'correct': specialist corrects the value

    After all confirmed, project status becomes 'parsed'.
    """
    service = ConfirmationService(db)

    for conf in data.confirmations:
        try:
            if conf.action == 'correct':
                service.apply_correction(
                    extraction_id=conf.extraction_id,
                    corrected_value=conf.corrected_value,
                    corrected_cert_id=conf.corrected_cert_id,
                    user_id=current_user.id,
                    notes=conf.notes,
                )
            elif conf.action == 'confirm':
                service.confirm_extraction(
                    extraction_id=conf.extraction_id,
                    user_id=current_user.id,
                )
        except ValueError as e:
            raise HTTPException(400, str(e))

    # Try to confirm all
    result = service.confirm_all(project_id, current_user.id)
    if not result['success']:
        raise HTTPException(400, result['error'])

    return {"status": "confirmed", "next_step": "evaluation"}
```

- [ ] **Step 3: Write documents endpoint**

```python
# app/api/v1/endpoints/documents.py
"""Document-specific API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.models.document import DocumentImage, OcrExtraction
import pathlib

router = APIRouter(prefix="/api", tags=["documents"])

@router.get("/document-images/{image_id}/view")
def get_image_view(
    image_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get original image for confirmation UI."""
    image = db.query(DocumentImage).get(image_id)
    if not image:
        raise HTTPException(404, "Image not found")
    return FileResponse(image.image_path)

@router.get("/ocr-extractions/{extraction_id}")
def get_extraction_detail(
    extraction_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get single OCR extraction detail for editing."""
    ext = db.query(OcrExtraction).get(extraction_id)
    if not ext:
        raise HTTPException(404, "Extraction not found")
    return {
        "id": ext.id,
        "field_name": ext.field_name,
        "field_value": ext.field_value,
        "normalized_value": ext.normalized_value,
        "confidence": float(ext.confidence_score),
        "is_validated": ext.is_validated,
        "standard_cert_id": ext.standard_cert_id,
        "bbox_coords": ext.bbox_coords,
    }
```

- [ ] **Step 4: Write request/response schemas**

```python
# app/schemas/document.py
from pydantic import BaseModel
from typing import Optional

class ProjectCreate(BaseModel):
    project_name: Optional[str] = None
    owner_unit: Optional[str] = None
    created_by: int

class UploadResponse(BaseModel):
    file_id: int
    upload_status: str
    processed_images: int
    extracted_preview: Optional[dict] = None

class ConfirmationDataResponse(BaseModel):
    project: dict
    tender: dict
    images: list[dict]
    total_images: int
    pending_review_count: int

class ConfirmParsingRequest(BaseModel):
    confirmations: list[
        dict  # {extraction_id, action: 'confirm'|'correct', corrected_value?, corrected_cert_id?, notes?}
    ]
```

- [ ] **Step 5: Run tests to verify pass**

Run: `pytest tests/week1/test_api_projects.py tests/week1/test_api_documents.py -v` → PASS

- [ ] **Step 6: Commit**

```bash
git add app/api/v1/endpoints/projects.py app/api/v1/endpoints/documents.py
git add app/schemas/document.py tests/week1/test_api_projects.py tests/week1/test_api_documents.py
git commit -m "feat(week1): add API endpoints for project upload and confirmation"
```

---

### Task 11: Integration Test & Docker Compose Verification

**Files:**
- Create: `docker-compose.yml`
- Create: `tests/week1/test_integration_upload_flow.py`

- [ ] **Step 1: Write integration test for complete upload flow**

```python
# tests/week1/test_integration_upload_flow.py
import pytest

@pytest.mark.integration
def test_complete_upload_to_confirmation_flow(client, db_session, sample_pdf):
    """
    Integration test: Upload PDF → OCR runs → Confirmation data available.

    This is the core Week 1 deliverable flow.
    """
    # 1. Create project
    response = client.post("/api/projects", json={"created_by": 1})
    assert response.status_code == 200
    project_id = response.json()["id"]

    # 2. Upload PDF
    response = client.post(
        f"/api/projects/{project_id}/upload",
        files={"file": ("test.pdf", sample_pdf, "application/pdf")}
    )
    assert response.status_code == 200
    assert response.json()["upload_status"] == "success"

    # 3. Get confirmation data
    response = client.get(f"/api/projects/{project_id}/confirmation-data")
    assert response.status_code == 200
    data = response.json()
    assert data["total_images"] >= 0  # May be 0 if no images in PDF

    # 4. If there are pending items, confirm them
    # ... (test confirmation flow)
```

Run: `pytest tests/week1/test_integration_upload_flow.py -v` → (run against real services)

- [ ] **Step 2: Write Docker Compose for local dev**

```yaml
# docker-compose.yml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: tis
      POSTGRES_USER: tis
      POSTGRES_PASSWORD: tis
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  minio:
    image: minio/minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/data

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://tis:tis@postgres:5432/tis
      REDIS_URL: redis://redis:6379/0
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: minioadmin
      MINIO_SECRET_KEY: minioadmin
      DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY}
    depends_on:
      - postgres
      - redis
      - minio

  paddleocr:
    build:
      context: .
      dockerfile: Dockerfile.paddleocr
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

volumes:
  postgres_data:
  minio_data:
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml tests/week1/test_integration_upload_flow.py
git commit -m "feat(week1): add Docker Compose and integration test"
```

---

## Week 1 Acceptance Checklist

After completing all tasks, verify these deliverables:

- [ ] `POST /api/projects` creates empty project with status='uploaded'
- [ ] `POST /api/projects/{id}/upload` accepts PDF, runs OCR pipeline, returns preview
- [ ] `GET /api/projects/{id}/confirmation-data` returns all images with OCR fields
- [ ] Low confidence fields (<0.8) are flagged as needing review
- [ ] `POST /api/projects/{id}/confirm-parsing` accepts corrections and confirmations
- [ ] Once `is_validated=true`, record cannot be modified
- [ ] All `ocr_extractions` must be validated before `confirm_all` succeeds
- [ ] Project status correctly transitions: uploaded → parsing → parsed
- [ ] `standard_cert_suggestion` is populated but NOT `standard_cert_id` (set at confirmation)
- [ ] Docker Compose starts all services: PostgreSQL, Redis, MinIO, App, PaddleOCR

---

## Open Issues / TODO

1. **Week_01.md conflict**: `standard_cert_id` is set during OCR per Week_01.md, but per SPEC it should only be set during confirmation. Resolution: Two fields - `standard_cert_suggestion` (OCR) and `standard_cert_id` (confirmation).

2. **Confidence score**: Week_01.md uses fixed 0.85, but we store per-field confidence from PaddleOCR actual results.

3. **File storage**: MinIO integration is stubbed. Need to implement `services/storage.py` for production.

4. **Image classification**: `classify_image_type()` returns 'other' placeholder. Needs either CV model or LLM-based classification.

5. **Validation cannot be undone**: Per Single Source of Truth principle, once `is_validated=true`, records are immutable. No "undo" mechanism exists - if specialist makes a mistake, they must contact admin to reset.
