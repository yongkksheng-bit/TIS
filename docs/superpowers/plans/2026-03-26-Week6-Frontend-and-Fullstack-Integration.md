# Week 6 Implementation Plan: 复盘系统 + 前端界面与全栈大联调 (RKE + Frontend)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Week 6's Review & Knowledge Evolution backend (4 DB tables, BidReviewEngine, rebid detection) AND scaffold the Vue 3 frontend that integrates all Week 1-5 APIs into a complete project lifecycle UI.

**Architecture:**
- **Backend (Week 6 RKE):** 4 new DB tables (`bid_outcomes`, `winning_dna`, `disqualification_traps`, `draft_revivals`, `knowledge_evolution_logs`), `BidReviewEngine` with win/loss/disqualification analysis, `DraftRevivalEngine`, `rebid_alert` endpoint, knowledge evolution endpoints
- **Frontend (Vue 3 SPA):** Vite + Vue 3 + TypeScript + Tailwind CSS, routing via Vue Router, state via Pinia, API client layer wrapping all Week 1-5 endpoints + Week 6 endpoints

**Tech Stack:** Vue 3 (Composition API) + TypeScript + Vite + Tailwind CSS + Vue Router 4 + Pinia + Axios | FastAPI (backend) + PyMuPDF + python-docx

---

## File Structure

```
# Backend — Week 6 RKE
alembic/versions/w006_add_review_tables.py
app/models/review.py              # BidOutcome, WinningDNA, DisqualificationTrap, DraftRevival, KnowledgeEvolutionLog
app/schemas/week6.py             # Request/response schemas
app/core/week6_review/
  __init__.py
  bid_review_engine.py           # BidReviewEngine (analyze win/loss/disqualification)
  draft_revival_engine.py         # DraftRevivalEngine (revive abandoned drafts)
app/api/v1/endpoints/review.py   # 6 new endpoints
tests/week6/                     # All Week 6 tests

# Frontend — Vue 3 SPA
frontend/                        # NEW — Vue 3 project root
  package.json
  vite.config.ts
  tsconfig.json
  tailwind.config.js
  src/
    main.ts
    App.vue
    router/index.ts             # Vue Router setup
    stores/
      projectStore.ts            # Pinia store for project state
      authStore.ts               # Mock auth (user role: specialist/boss)
    api/
      client.ts                 # Axios instance with base URL
      projects.ts              # Project list + CRUD
      documents.ts             # Upload + confirmation
      evaluations.ts           # Week 2 evaluation API
      rag.ts                   # Week 3 RAG API
      pricing.ts               # Week 4 pricing API
      formalReview.ts          # Week 5 formal review API
      review.ts               # Week 6 review API
    views/
      DashboardView.vue        # Project card list
      ProjectUploadView.vue     # PDF upload + OCR trigger
      ConfirmationView.vue     # OCR confirmation (Week 1)
      EvaluationView.vue        # Qualification screening (Week 2)
      TechProposalView.vue      # RAG generation (Week 3)
      PricingView.vue          # Cost + game theory (Week 4)
      FormalReviewView.vue      # Review checklist (Week 5)
      FinalOutputView.vue       # Word generation + download (Week 5)
      ReviewView.vue            # Bid outcome entry + analysis (Week 6)
    components/
      ProjectCard.vue
      StatusBadge.vue
      ReviewItemCard.vue
      PricingScenarioCard.vue
      DocxDownloadButton.vue
    types/
      index.ts                 # Shared TypeScript interfaces mirroring backend schemas
```

**Existing files to modify:**
- `app/main.py`: add `review.router`
- `app/models/__init__.py`: add review models
- `app/api/v1/endpoints/__init__.py`: add review

---

## Dependency Chain

```
Backend Task 1 (Migration+Models+Schemas) → Backend Task 2 (BidReviewEngine)
Backend Task 2 → Backend Task 3 (API Endpoints)
                                                                       ↓
Frontend Task 4 (Scaffold+Vite+Types) → Frontend Task 5 (API Client Layer)
Frontend Task 5 → Frontend Task 6 (Dashboard + Upload + Confirmation)
Frontend Task 6 → Frontend Task 7 (Evaluation + TechProposal)
Frontend Task 7 → Frontend Task 8 (Pricing + FormalReview + FinalOutput)
Frontend Task 8 → Frontend Task 9 (Review + Rebid Alert)
Frontend Task 9 → Frontend Task 10 (E2E Full-Stack Integration Test)
```

**Mock vs Real API strategy:**
- Development (Tasks 4-7): Mock Pinia stores with hardcoded JSON — no backend needed
- Backend联调 (Tasks 8-10): Flip `VITE_USE_MOCK=false` in `.env`, point `VITE_API_BASE_URL=http://localhost:8000`, run real FastAPI

---

## Backend — Week 6 RKE

### Task 1: Migration + Models + Schemas

**Files:**
- Create: `alembic/versions/w006_add_review_tables.py`
- Create: `app/models/review.py`
- Create: `app/schemas/week6.py`
- Modify: `app/models/__init__.py`

- [ ] **Step 1: Write migration test skeleton**

Create `tests/week6/test_week6_migrations.py`:

```python
"""TDD tests for Week 6 review tables migration."""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(100))"))
        conn.execute(text("CREATE TABLE projects (id INTEGER PRIMARY KEY, project_name VARCHAR(255), status VARCHAR(50))"))
        conn.execute(text("CREATE TABLE formal_review_items (id INTEGER PRIMARY KEY, project_id INTEGER, risk_level VARCHAR(20), specialist_status VARCHAR(20))"))
        conn.execute(text("CREATE TABLE knowledge_chunks (id INTEGER PRIMARY KEY, quality_score INTEGER, usage_count INTEGER, is_deprecated INTEGER)"))
        conn.execute(text("CREATE TABLE abandoned_drafts (id INTEGER PRIMARY KEY, project_id INTEGER)"))
        conn.execute(text("CREATE TABLE pricing_decisions (id INTEGER PRIMARY KEY, project_id INTEGER, boss_final_price NUMERIC(15,2))"))
        conn.commit()
    return engine


class TestBidOutcomesTable:
    def test_table_exists(self, db_engine): ...
    def test_all_columns(self, db_engine): ...
    def test_outcome_status_check(self, db_engine): ...
    def test_disqualification_type_check(self, db_engine): ...
    def test_project_fk_cascade(self, db_engine): ...


class TestWinningDNATable:
    def test_table_exists(self, db_engine): ...
    def test_dna_type_check(self, db_engine): ...


class TestDisqualificationTrapsTable:
    def test_table_exists(self, db_engine): ...
    def test_trap_category_check(self, db_engine): ...


class TestDraftRevivalsTable:
    def test_table_exists(self, db_engine): ...
    def test_revive_type_check(self, db_engine): ...
```

Write 15 migration tests total.

- [ ] **Step 2: Run tests — should FAIL**

Run: `pytest tests/week6/test_week6_migrations.py -v` → FAIL

- [ ] **Step 3: Write migration**

Create `alembic/versions/w006_add_review_tables.py`:

```python
"""Week 6: bid_outcomes, winning_dna, disqualification_traps, draft_revivals, knowledge_evolution_logs."""
from alembic import op
import sqlalchemy as sa

revision = 'w006'
down_revision = 'w005'
branch_labels = None
depends_on = None


def upgrade():
    # bid_outcomes
    op.create_table('bid_outcomes', ...)
    # winning_dna
    op.create_table('winning_dna', ...)
    # disqualification_traps
    op.create_table('disqualification_traps', ...)
    # draft_revivals
    op.create_table('draft_revivals', ...)
    # knowledge_evolution_logs
    op.create_table('knowledge_evolution_logs', ...)


def downgrade():
    op.drop_table('knowledge_evolution_logs')
    op.drop_table('draft_revivals')
    op.drop_table('disqualification_traps')
    op.drop_table('winning_dna')
    op.drop_table('bid_outcomes')
```

- [ ] **Step 4: Run migration tests — should PASS**

Run: `pytest tests/week6/test_week6_migrations.py -v` → 15/15 PASS

- [ ] **Step 5: Write model tests + models**

Create `tests/week6/test_review_models.py` — test BidOutcome, WinningDNA, DisqualificationTrap, DraftRevival with in-memory SQLite.

Create `app/models/review.py` with SQLAlchemy models:
```python
class BidOutcome(Base):
    __tablename__ = "bid_outcomes"
    # (see Week_06.md §2 for full column list)

class WinningDNA(Base):
    __tablename__ = "winning_dna"

class DisqualificationTrap(Base):
    __tablename__ = "disqualification_traps"

class DraftRevival(Base):
    __tablename__ = "draft_revivals"

class KnowledgeEvolutionLog(Base):
    __tablename__ = "knowledge_evolution_logs"
```

- [ ] **Step 6: Write schema tests + schemas**

Create `tests/week6/test_week6_schemas.py` — test BidOutcomeRecordRequest, ReviewAnalysisResponse, RebidAlertResponse, etc.

Create `app/schemas/week6.py` — Pydantic schemas mirroring the API definitions in Week_06.md §4.

- [ ] **Step 7: Run all Week 6 tests — verify PASS**

- [ ] **Step 8: Run Week 3/4/5 regression — must be 100% green**

- [ ] **Step 9: Commit**

```bash
git add alembic/versions/w006*.py app/models/review.py app/schemas/week6.py
git add tests/week6/test_week6_migrations.py tests/week6/test_review_models.py tests/week6/test_week6_schemas.py
git commit -m "feat(week6): add bid_outcomes, winning_dna, disqualification_traps tables and models"
```

---

### Task 2: BidReviewEngine + DraftRevivalEngine

**Files:**
- Create: `app/core/week6_review/__init__.py`
- Create: `app/core/week6_review/bid_review_engine.py`
- Create: `app/core/week6_review/draft_revival_engine.py`
- Create: `tests/week6/test_bid_review_engine.py`

- [ ] **Step 1: Write BidReviewEngine tests**

```python
"""TDD tests for BidReviewEngine."""
from unittest.mock import MagicMock

class TestBidReviewEngine:
    def test_analyze_win_creates_dna_and_updates_quality(self): ...
    def test_analyze_disqualification_links_to_review_item(self): ...
    def test_analyze_loss_records_to_price_history(self): ...
    def test_detect_manual_error_when_specialist_deleted_item(self): ...
```

And DraftRevivalEngine tests:
```python
class TestDraftRevivalEngine:
    def test_revive_calculates_reusability(self): ...
    def test_revive_for_rebid_returns_content_list(self): ...
```

- [ ] **Step 2: Run tests — should FAIL**

- [ ] **Step 3: Write engines**

**BidReviewEngine** (`bid_review_engine.py`):
- `__init__(db, project_id)` — load project, outcome, pricing, tech_proposal
- `auto_analyze()` → calls `_analyze_win()` / `_analyze_loss()` / `_analyze_disqualification()`
- `_analyze_win()`: calculate discount_rate, insert into price_history, extract winning DNA, upgrade knowledge_chunks quality_score +20
- `_analyze_disqualification()`: link to formal_review_items, detect manual error (specialist_status='deleted' + outcome='disqualified')
- `_update_trap_library()`: upsert into disqualification_traps

**DraftRevivalEngine** (`draft_revival_engine.py`):
- `revive_for_rebid(abandoned_draft_id, new_project_id)` — parse old tech proposal, calculate reusability per section, import reusable sections to knowledge_chunks, record in draft_revivals

- [ ] **Step 4: Run engine tests — should PASS**

- [ ] **Step 5: Run regression — must be green**

- [ ] **Step 6: Commit**

---

### Task 3: Review API Endpoints

**Files:**
- Create: `app/api/v1/endpoints/review.py`
- Modify: `app/main.py`, `app/api/v1/endpoints/__init__.py`

Implement these endpoints (prefix `/api/v1`):

1. `POST /projects/{project_id}/outcomes/record` — record bid outcome + trigger auto_analyze
2. `GET /projects/{project_id}/review-analysis` — get auto analysis result
3. `POST /projects/{project_id}/review-analysis/confirm` — confirm analysis, trigger knowledge evolution
4. `GET /projects/{new_project_id}/rebid-alert` — detect if new project is similar to historical project
5. `POST /revivals/{abandoned_draft_id}/revive-to/{new_project_id}` — execute draft revival
6. `GET /knowledge-base/evolution-report` — return knowledge stats for dashboard

Write 10 API tests for these endpoints.

- [ ] **Commit**

---

## Frontend — Vue 3 SPA

### Task 4: Frontend Scaffold + TypeScript Types + API Client

**Files:**
- Create: `frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `tailwind.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.ts`, `frontend/src/App.vue`
- Create: `frontend/src/router/index.ts`
- Create: `frontend/src/stores/projectStore.ts`, `frontend/src/stores/authStore.ts`
- Create: `frontend/src/api/client.ts` (Axios base)
- Create: `frontend/src/types/index.ts`

- [ ] **Step 1: Write package.json and config files**

`package.json` dependencies:
```json
{
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.0",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.0.0",
    "typescript": "^5.3.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "@types/node": "^20.0.0"
  }
}
```

`vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true }
    }
  }
})
```

- [ ] **Step 2: Write TypeScript types** — mirror all backend response schemas

`types/index.ts`:
```typescript
export interface Project {
  id: number
  project_name: string
  project_type: string
  owner_unit: string
  region: string
  budget_amount: number
  status: ProjectStatus
  relationship_flag: boolean
  generation_mode: string
  bid_open_date: string
}

export type ProjectStatus = 'uploaded' | 'parsing' | 'parsed' | 'evaluating' |
  'evaluation_ready' | 'worthy' | 'unworthy' | 'generating_documents' |
  'awaiting_pricing' | 'awaiting_review' | 'completed' | 'terminated_by_boss'

export interface BidOutcome {
  id: number
  project_id: number
  outcome_status: 'win' | 'lose' | 'disqualified'
  final_bid_price: number
  winning_price?: number
  review_analysis?: ReviewAnalysis
}

export interface ReviewAnalysis {
  type: 'win' | 'lose' | 'disqualification'
  detected_trap?: string
  is_manual_error?: boolean
  dna_extracted?: number[]
  price_strategy?: PriceStrategy
}

export interface RebidAlert {
  is_rebid: boolean
  historical_project_id?: number
  historical_outcome?: string
  warnings: string[]
  revivable_drafts?: RevivableDraft[]
}
```

- [ ] **Step 3: Write Axios API client**

`api/client.ts`:
```typescript
import axios from 'axios'
const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
})
client.interceptors.response.use(r => r.data)
export default client
```

Then per-domain API files (`api/projects.ts`, `api/pricing.ts`, etc.) — each exports typed functions calling `client.get/post(path)`.

- [ ] **Step 4: Write Pinia stores**

`stores/projectStore.ts` — manages `projects[]`, `currentProject`, `fetchProjects()`, `fetchProject(id)`, `createProject(data)`, `updateProjectStatus(id, status)`.

`stores/authStore.ts` — manages `currentUser: {id, username, role: 'specialist' | 'boss' | 'finance'}`. Mock implementation with localStorage persistence.

- [ ] **Step 5: Write Vue Router setup**

```typescript
const routes = [
  { path: '/', component: DashboardView },
  { path: '/projects/:id/upload', component: ProjectUploadView },
  { path: '/projects/:id/confirm', component: ConfirmationView },
  { path: '/projects/:id/evaluation', component: EvaluationView },
  { path: '/projects/:id/tech-proposal', component: TechProposalView },
  { path: '/projects/:id/pricing', component: PricingView },
  { path: '/projects/:id/formal-review', component: FormalReviewView },
  { path: '/projects/:id/output', component: FinalOutputView },
  { path: '/projects/:id/review', component: ReviewView },
]
```

- [ ] **Step 6: Write App.vue shell + NavBar**

App.vue has `<NavBar>` + `<router-view>`. NavBar shows project name + status breadcrumb. Role-based nav items (specialist sees all, boss sees overview + approve, finance sees pricing).

- [ ] **Step 7: Verify build**

Run: `cd frontend && npm install && npm run build` → should succeed with 0 errors

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat(week6): scaffold Vue 3 + TypeScript + Tailwind frontend project"
```

---

### Task 5: Dashboard View + Project Card Components

**Files:**
- Create: `frontend/src/views/DashboardView.vue`
- Create: `frontend/src/components/ProjectCard.vue`
- Create: `frontend/src/components/StatusBadge.vue`

- [ ] **Step 1: Write ProjectCard component**

```vue
<!-- ProjectCard.vue -->
<template>
  <div class="project-card border rounded-lg p-4" :class="borderColor">
    <h3 class="font-semibold">{{ project.project_name }}</h3>
    <StatusBadge :status="project.status" />
    <p class="text-sm text-gray-500">{{ project.owner_unit }} · {{ project.region }}</p>
    <p class="text-sm">预算: ¥{{ formatMoney(project.budget_amount) }}</p>
    <router-link :to="`/projects/${project.id}/upload`" class="btn-primary mt-2">
      {{ actionLabel }}
    </router-link>
  </div>
</template>
```

StatusBadge uses colors: green=worthy/completed, yellow=in-progress, red=unworthy/terminated, grey=uploaded.

- [ ] **Step 2: Write DashboardView**

Fetches projects from API (or mock), renders grid of ProjectCards. Has "新建项目" button (POST /api/projects). Shows filter tabs: All / In Progress / Completed / Discarded.

- [ ] **Step 3: Verify locally with mock data**

- [ ] **Commit**

---

### Task 6: Upload + OCR + Confirmation Views

**Files:**
- Create: `frontend/src/views/ProjectUploadView.vue`
- Create: `frontend/src/views/ConfirmationView.vue`

**ProjectUploadView:**
- Drag-and-drop file upload (use `@submit.prevent` + `FormData`)
- POST to `/api/projects/{id}/upload`
- Show parsing progress (polling or spinner)
- On success → navigate to `/projects/{id}/confirm`

**ConfirmationView (Week 1):**
- GET `/api/projects/{id}/confirmation-data`
- Display OCR results as editable rows
- Buttons: Confirm All / Correct Value / Skip
- POST `/api/projects/{id}/confirm-parsing`
- On success → navigate to `/projects/{id}/evaluation`

**Mock strategy:** Until backend is ready, use `projectStore.mockConfirmationData = [...]` to render the UI.

- [ ] **Commit**

---

### Task 7: Evaluation + TechProposal Views

**Files:**
- Create: `frontend/src/views/EvaluationView.vue`
- Create: `frontend/src/views/TechProposalView.vue`
- Create: `frontend/src/components/QualificationBadge.vue` (green/yellow/red for cert status)

**EvaluationView (Week 2):**
- GET `/api/v1/projects/{id}/evaluations/latest` → show qualification score, time urgency, win probability
- Display red/yellow/green list of certs (matched/missing/warning)
- Show relationship_index gauge
- Buttons: "提交 worthy" / "提交 unworthy" → POST `/api/v1/evaluations/{report_id}/approve`
- For boss: override button → POST `/api/v1/evaluations/{report_id}/override`

**TechProposalView (Week 3):**
- Toggle AUTO/GUIDED mode
- POST `/api/v1/projects/{id}/documents/embed` → embed tender doc
- For each scoring section: POST `/api/v1/projects/{id}/sections/generate` → show generated content
- Inline edit capability (textarea, regenerate button)
- Show generation progress (mock with setTimeout for V1)
- On confirm: navigate to `/projects/{id}/pricing`

- [ ] **Commit**

---

### Task 8: Pricing + FormalReview + FinalOutput Views

**Files:**
- Create: `frontend/src/views/PricingView.vue`
- Create: `frontend/src/views/FormalReviewView.vue`
- Create: `frontend/src/views/FinalOutputView.vue`
- Create: `frontend/src/components/PricingScenarioCard.vue`
- Create: `frontend/src/components/ReviewItemCard.vue`

**PricingView (Week 4):**
- Cost entry form (food/labor/logistics/management/other) → POST `/api/v1/projects/{id}/cost-estimates`
- Confirm cost → POST `/api/v1/cost-estimates/{id}/confirm`
- View A/B/C scenarios from GET `/api/v1/projects/{id}/pricing-calculations`
- PricingScenarioCard: shows price, win_prob, expected_value, is_recommended badge
- Boss final price input → POST `/api/v1/projects/{id}/pricing-decisions`
- Navigate to `/projects/{id}/formal-review`

**FormalReviewView (Week 5):**
- GET `/api/v1/projects/{id}/formal-review/status` → show aggregate (can_generate, fatal_pending)
- GET `/api/v1/projects/{id}/formal-review/items` → list ReviewItemCards
- ReviewItemCard: shows risk color (red/yellow/green), check_title, system_status
- Action buttons: Confirm / Correct (with evidence textarea) / Delete (with notes)
- POST `/api/v1/formal-review-items/{id}/confirm|correct|delete`
- POST `/api/v1/projects/{id}/formal-review/manual-add` for adding extra checks
- If can_generate=true: show green "生成最终标书" button

**FinalOutputView (Week 5):**
- POST `/api/v1/projects/{id}/final-documents/generate`
- Show loading spinner during generation
- On success: display file path + download link
- Show packaging_guide checklist (checklist UI)
- Download button for Word doc

- [ ] **Commit**

---

### Task 9: Review + RebidAlert View

**Files:**
- Create: `frontend/src/views/ReviewView.vue`
- Create: `frontend/src/components/RebidAlertBanner.vue`

**ReviewView (Week 6):**
- GET `/api/v1/projects/{id}/review-analysis`
- If no outcome recorded: show outcome entry form (win/lose/disqualified, final_bid_price, winning_price, disqualification_reason)
- POST `/api/v1/projects/{id}/outcomes/record` → triggers auto analysis
- Display analysis result:
  - Win: show DNA extracted count, price strategy
  - Lose: show price comparison
  - Disqualified: show detected trap, manual error warning
- Confirm button → POST `/api/v1/projects/{id}/review-analysis/confirm`

**RebidAlertBanner:**
- GET `/api/v1/projects/{id}/rebid-alert` (called on project creation/upload)
- If `is_rebid=true`: show colored banner (red=yellow=disqualification history, green=win history)
- Show historical outcome + warnings
- Show revivable drafts list with "复活" buttons

- [ ] **Commit**

---

### Task 10: E2E Full-Stack Integration Test + Regression

**Files:**
- Create: `tests/week6/test_week6_backend_api.py` — backend API tests for Week 6
- Modify: (no frontend test file needed — E2E verified via manual browser testing)

- [ ] **Step 1: Run Week 6 backend API tests**

Run: `pytest tests/week6/ -v` → all must pass

- [ ] **Step 2: Run Week 3/4/5 regression**

Run: `pytest tests/week3/ tests/week4/ tests/week5/ -v` → all 100% green

- [ ] **Step 3: Verify frontend builds without errors**

Run: `cd frontend && npm run build` → 0 errors

- [ ] **Step 4: Manual E2E checklist** (document this as a README in frontend/):

```
E2E Verification Steps:
1. npm run dev (frontend on :3000) + uvicorn app.main --reload (backend on :8000)
2. Create project → upload PDF → OCR confirmation
3. Generate evaluation → specialist approves
4. Generate tech proposal (AUTO mode) → confirm sections
5. Enter costs → confirm → view pricing scenarios → boss sets final price
6. Run formal review → confirm items → generate final Word doc
7. Enter bid outcome (win/disqualify) → verify knowledge evolution
```

- [ ] **Step 5: Commit**

```bash
git add tests/week6/
git commit -m "test(week6): add Week 6 backend API tests"
```

---

## Summary

| Task | Component | New Files | Tests |
|------|-----------|-----------|-------|
| 1 | Migration+Models+Schemas | w006 migration, review.py, week6.py | ~25 |
| 2 | BidReviewEngine + DraftRevivalEngine | bid_review_engine.py, draft_revival_engine.py | ~8 |
| 3 | Review API Endpoints | review.py | ~10 |
| 4 | Frontend Scaffold + Types + API Client | frontend/* (20+ files) | N/A |
| 5 | Dashboard + ProjectCard | DashboardView.vue, ProjectCard.vue | N/A |
| 6 | Upload + Confirmation Views | ProjectUploadView.vue, ConfirmationView.vue | N/A |
| 7 | Evaluation + TechProposal Views | EvaluationView.vue, TechProposalView.vue | N/A |
| 8 | Pricing + FormalReview + FinalOutput | PricingView.vue, FormalReviewView.vue, FinalOutputView.vue | N/A |
| 9 | Review + RebidAlert View | ReviewView.vue, RebidAlertBanner.vue | N/A |
| 10 | E2E Integration + Regression | test_week6_backend_api.py | ~10 |
| **Total** | | **~60 new files** | **~53 backend tests** |

**Mock/Real API Strategy:**
- Tasks 4-7: `VITE_USE_MOCK=true` (default) — frontend works with hardcoded Pinia state
- Tasks 8-10: `VITE_USE_MOCK=false VITE_API_BASE_URL=http://localhost:8000` — real FastAPI integration

**Regression Gates:** Week 3 (105) + Week 4 (53) + Week 5 (58) must remain 100% green throughout.
