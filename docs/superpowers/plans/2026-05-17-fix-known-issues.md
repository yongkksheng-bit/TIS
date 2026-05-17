# 修复 3 个已知小毛病 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:systematic-debugging (for Task 1 root cause) and superpowers:test-driven-development (for Task 3 startup check). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 3 个已知小毛病：API路径不一致、状态命名不一致、启动时 users 表健康检查

**Architecture:** 三个独立修复，分别在后端路由、前端调用、文档、启动事件

---

## 任务1：统一 API 路径版本（P1）

### Files
- Modify: `app/api/v1/endpoints/projects.py:13` (router prefix from `/api/projects` → `/api/v1/projects`)
- Modify: `app/main.py:44` (remove `projects.router` since it's being merged into v1)
- Verify: `scripts/daily_smoke_test.sh:198,441`
- Verify: `frontend/src/views/TechProposalView.vue:242` (already uses `/api/v1/projects/...`)

### Root Cause Analysis (Phase 1)

**Pattern Found:**
- `projects.router` (in `app/api/v1/endpoints/projects.py`): prefix `/api/projects`
  - All 15 endpoints under this router use this prefix
  - `advance-to-pricing` is at `/api/projects/{id}/advance-to-pricing`
- `TechProposalView.vue:242`: calls `/api/v1/projects/${projectId.value}/advance-to-pricing`
- Nginx: `location /api/` → `http://backend:8000$request_uri`

**The Mismatch:**
- Frontend calls `/api/v1/projects/3/advance-to-pricing`
- nginx sends to FastAPI: `http://backend:8000/api/v1/projects/3/advance-to-pricing`
- FastAPI route: `/api/projects/3/advance-to-pricing` → **404**

But smoke test finds it works. Let's trace why.

**Verification:**
```bash
# Check if v1/projects has the endpoint
curl -s http://localhost:8000/api/v1/projects/3/advance-to-pricing
# vs
curl -s http://localhost:8000/api/projects/3/advance-to-pricing
```

### Fix: Move `advance-to-pricing` to v1 router

**BUT WAIT:** `projects.router` has 15 endpoints, only `advance-to-pricing` uses inconsistent path. Moving all 15 endpoints to v1 would be disruptive.

**Alternative Analysis:**
- Most v1 endpoints are already at `/api/v1/projects/...`
- `projects.router` is the OLD way, BEFORE v1 versioning was introduced
- New endpoints (pricing, formal_review, rag) all use `/api/v1/projects/...`
- Only `advance-to-pricing` in `projects.router` conflicts

**Selected Approach:** Change `projects.router` prefix from `/api/projects` to `/api/v1/projects` to align with other v1 endpoints.

### Implementation Steps

- [ ] **Step 1: Verify current state with curl**
```bash
# Test current paths
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/projects/3/advance-to-pricing
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/projects/3/advance-to-pricing
```

- [ ] **Step 2: Modify projects.py router prefix**
```python
# app/api/v1/endpoints/projects.py:13
router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
```

- [ ] **Step 3: Update main.py to remove projects.router** (since it's now under v1)
```python
# app/main.py:44 - remove projects.router from include_router list
# The endpoint is now at /api/v1/projects/... under v1/projects router
```

- [ ] **Step 4: Verify no duplicate route registration**
```bash
grep -rn "projects.router\|include_router.*projects" app/
```

- [ ] **Step 5: Update daily_smoke_test.sh paths** (both Path A and Path B Step 9)
```bash
# scripts/daily_smoke_test.sh:198,441
# Change: /api/projects/$PROJECT_ID_A/advance-to-pricing
# To:     /api/v1/projects/$PROJECT_ID_A/advance-to-pricing
```

- [ ] **Step 6: Verify TechProposalView.vue** (should already use correct path)
```bash
grep -n "advance-to-pricing" frontend/src/views/TechProposalView.vue
```

- [ ] **Step 7: Rebuild backend container**
```bash
docker compose build --no-cache backend
docker compose up -d backend
```

- [ ] **Step 8: Verify with curl**
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/projects/3/advance-to-pricing
# Expected: 200 or 400 (not 404)
```

- [ ] **Step 9: Run smoke test Path A Step 9**
```bash
# Full test in scripts/daily_smoke_test.sh
```

---

## 任务2：统一状态命名（P2）

### Files
- Modify: `docs/superpowers/plans/2026-05-14-final-verification-plan.md`

### Root Cause Analysis

**Code Reality:**
- `ProjectStatus.EVALUATING = "evaluating"` (line 8 in enums.py)
- `ProjectStatus.EVALUATION_READY = "evaluation_ready"` (line 9 in enums.py)
- `confirmation_service.py:176` sets `project.status = 'evaluating'` (not `evaluation_ready`)
- Two SEPARATE states exist in code

**Actual Workflow:**
```
confirm-parsing success → project.status = 'evaluating' (NOT evaluation_ready)
evaluating → generating_documents (after approval)
```

So the doc should reference `evaluating`, not `evaluation_ready`.

### Implementation Steps

- [ ] **Step 1: Confirm code uses `evaluating` not `evaluation_ready`**
```bash
grep -rn "project.status.*evaluating\|project.status.*evaluation_ready" app/
```

- [ ] **Step 2: Update 2026-05-14-final-verification-plan.md**
- Replace all `evaluation_ready` → `evaluating`
- Add comment at Step 4: `# 注意：API 返回 "evaluating"，数据库 status 字段也是 "evaluating"`

- [ ] **Step 3: Verify no other docs reference `evaluation_ready`**
```bash
grep -rn "evaluation_ready" docs/superpowers/ --include="*.md"
```

---

## 任务3：启动时 users 表健康检查（P2）

### Files
- Create: `tests/test_startup_health.py` (new test file)
- Modify: `app/main.py` (add startup event)
- Verify: `app/db/seed.py` already has `seed_demo_user()`

### Test-First Approach (TDD)

- [ ] **Step 1: Write failing test**
```python
# tests/test_startup_health.py
import pytest
from app.models.user import User
from app.db.session import SessionLocal

def test_ensure_demo_user_idempotent():
    """Demo user creation is idempotent - running twice doesn't error."""
    # Arrange
    db = SessionLocal()
    # Clean up if exists
    existing = db.query(User).filter(User.id == 1).first()
    if existing:
        db.delete(existing)
        db.commit()

    # Act - call ensure twice
    from app.db.seed import ensure_demo_user
    ensure_demo_user()
    ensure_demo_user()  # second call should not error

    # Assert
    user = db.query(User).filter(User.id == 1).first()
    assert user is not None
    assert user.username == "specialist"
    db.close()
```

- [ ] **Step 2: Run test to verify RED**
```bash
cd D:/tis_project
python -m pytest tests/test_startup_health.py -v
# Expected: FAIL - function not found
```

- [ ] **Step 3: Check if `ensure_demo_user` exists in seed.py**
```bash
grep -n "def ensure_demo_user\|def seed_demo_user" app/db/seed.py
```

- [ ] **Step 4: If only `seed_demo_user` exists, add wrapper**
```python
# app/db/seed.py
def ensure_demo_user():
    """Ensure demo user exists, idempotent."""
    seed_demo_user()  # seed_demo_user already handles idempotency
```

- [ ] **Step 5: Run test to verify GREEN**
```bash
python -m pytest tests/test_startup_health.py -v
# Expected: PASS
```

- [ ] **Step 6: Add startup event to main.py**
```python
# app/main.py
from app.db.seed import ensure_demo_user

@app.on_event("startup")
async def startup_event():
    logger = get_logger("startup")
    try:
        ensure_demo_user()
        logger.info("Demo user ensured on startup")
    except Exception as e:
        logger.error(f"Failed to ensure demo user: {e}")
        # Non-blocking: log only, don't crash startup
```

- [ ] **Step 7: Verify no blocking startup**
```bash
# Restart backend container
docker compose restart backend
docker logs tis_backend --tail 20 | grep -i "demo user\|startup"
```

- [ ] **Step 8: Manual test - delete demo user and restart**
```python
# In backend container or psql
DELETE FROM users WHERE id = 1;
# Then restart backend, verify it recreates
```

---

## Verification Checklist

| Task | Verification | Expected Result |
|------|--------------|-----------------|
| 1 | `curl /api/v1/projects/3/advance-to-pricing` | 200 or 400 (not 404) |
| 1 | Smoke test Path A Step 9 | PASS |
| 2 | Grep `evaluation_ready` in plan doc | 0 matches |
| 3 | Delete user id=1, restart backend | User recreated |
| 3 | pytest tests/week2/ | 0 regressions |

---

## Commit Strategy

After each task verification:
```bash
# Task 1
git add app/api/v1/endpoints/projects.py app/main.py scripts/daily_smoke_test.sh
git commit -m "fix(api): unify advance-to-pricing path to /api/v1/projects/"

# Task 2
git add docs/superpowers/plans/2026-05-14-final-verification-plan.md
git commit -m "docs: standardize status naming to 'evaluating'"

# Task 3
git add app/main.py tests/test_startup_health.py app/db/seed.py
git commit -m "feat(startup): add demo user health check on backend startup"
```