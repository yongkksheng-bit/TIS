# 项目事实 | 龙虾记忆

> **客观事实** - 数据库表名、接口路由、配置参数等客观信息

---

## 记忆卡片格式

每个记忆条目使用以下 YAML 头部：

```yaml
### [记忆条目标题]
- **Type**: 事实
- **Score**: 0.0-1.0
- **Date**: YYYY-MM-DD
- **Status**: Active / Archived
---
```

---

## 项目客观事实

### Docker 统一物理拓扑（2026-03-30 修正）

- **Type**: 事实
- **Score**: 1.0
- **Date**: 2026-03-30
- **Status**: Active
---
⚠️ 端口 8001 曾被误记为 Docker 映射端口，实际 8000 才是 Docker backend 直连。
---
**物理容器节点：**

| 服务 | 容器名 | 物理端口 | 容器端口 | 数据卷 |
|------|--------|----------|----------|--------|
| PostgreSQL+pgvector | `tis_db` | **5433** | 5432 | `postgres_data` |
| Redis | `tis_redis` | 6379 | 6379 | `redis_data` |
| MinIO | `tis_minio` | 9000/9001 | 9000/9001 | `minio_data` |
| FastAPI Backend | `tis_backend` | **8000** | 8000 | (无持久卷，代码即镜像) |
| Vue3 Frontend (Nginx) | `tis_frontend` | 3000 | 80 | (无持久卷，dist 即镜像) |

**内部网络：** `tis_project_tis_net`（bridge driver）

**前后端访问双入口（关键）：**

| 调用方 | 访问地址 | 路由说明 |
|--------|----------|----------|
| 浏览器（前端 SPA） | `http://localhost:3000` | Vue3 页面 |
| 浏览器（API 调用） | `http://localhost:3000/api/...` | Nginx 反向代理 → `tis_backend:8000` |
| Playwright / curl（直连） | `http://localhost:8000` | Docker 端口直连后端 |

**数据库连接字符串（容器内）：**
```
postgresql://postgres:Syk0215@db:5432/canteen_system
```

**关键运维命令：**
```bash
# 重启后网络隔离修复（如需要）
docker network connect tis_project_tis_net tis_backend
docker network connect tis_project_tis_net tis_frontend

# 启动（默认端口 8000）
docker compose up -d
```

---

### API 路由前缀规范（2026-03-29 锁定）

- **Type**: 事实
- **Score**: 1.0
- **Date**: 2026-03-29
- **Status**: Active
---
**axios `apiClient` 配置：**
- `baseURL = '/api'`（由 Vite 代理，在 Docker 中通过 nginx 转发）

**FastAPI 路由前缀：**
| 路由文件 | 路由前缀 | 示例 |
|----------|----------|------|
| `projects.py` | `/api/projects` | `GET /api/projects/{id}` |
| `rag.py` | `/api/v1/projects` | `POST /api/v1/projects/{id}/generate-section` |

**因此前端调用时路径规则：**
- `projects.py` 的路径 → 前端写 `/projects/...`（自动拼接 `/api`）
- `rag.py` 的路径 → 前端写 `/v1/projects/...`（自动拼接 `/api`）

**错误写法（双重前缀）：** `/api/projects/...` → 实际变成 `/api/api/projects/...` → 404

**已确认不含双重前缀的文件：**
- `ConfirmationView.vue`（已修复：`/projects/{id}/confirmation-data`）
- `ProjectUploadView.vue`（已修复：`/projects`）
- `TechProposalView.vue`（已修复：`/v1/projects/{id}/sections`）
- `projectStore.ts`（已修复：`/projects/${id}`）

---

### 资质评估算分规则（2026-03-30 实测锁定）

- **Type**: 事实
- **Score**: 1.0
- **Date**: 2026-03-30
- **Status**: Active
---
**核心原则：** 提取失败 ≠ 100 分，真实 0 分 + fatal risk

**算分决策树：**
```
tender_reqs == []?
  → score=0, SYSTEM_EXTRACTION_FAILED (fatal)
  → is_extraction_valid = false

total_mandatory == 0 AND matched_optional == 0 AND total_optional > 0?
  → score=0, SYSTEM_CERT_EXTRACTION_FAILED (fatal)
  → is_extraction_valid = false

total_mandatory == 0 AND matched_optional > 0?
  → score = int((matched_optional / total_optional) * 100)
  → is_extraction_valid = true

total_mandatory > 0?
  → score = int((matched_mandatory / total_mandatory) * 100)
  → has_fatal = missing OR expired OR wrong_cert_blocked_by_exclude OR qualification_requirements_not_extracted OR cert_extraction_failed
```

**新增返回字段（2026-03-30）：**
- `qualification_match_score`: 0-100
- `is_qualification_pass`: `qualification_match_score >= 60 AND NOT has_fatal`
- `is_extraction_valid`: `bool(tender_reqs)`（TenderDocument 存在且有数据）
- `recommendation`: `score=0 → abandon`，`score>0 && <60 → conditional`，`score>=60 → worth_bidding`

**涉及文件：**
- `qualification_matcher.py` — 算分引擎
- `evaluation_engine.py` — 推荐决策 + 报告持久化

---

### RAG 生成接口（2026-03-29 实测）

- **Type**: 事实
- **Score**: 0.9
- **Date**: 2026-03-29
- **Status**: Active
---
**端点：** `POST /api/v1/projects/{project_id}/generate-section`

**请求体：**
```json
{
  "section_name": "项目理解",
  "generation_mode": "auto",
  "insider_notes": null,
  "top_k": 5
}
```

**响应（实测，DeepSeek 模拟模式）：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "project_id": 6,
    "section_name": "项目理解",
    "content": "[AUTO MODE RESPONSE]\n这是一个模拟的投标技术标内容...",
    "mode": "auto",
    "token_usage": {"prompt_tokens": 54, "completion_tokens": 23, "total_tokens": 78},
    "source_chunk_count": 0,
    "generation_timestamp": "2026-03-29T12:37:11Z"
  }
}
```

**Element Plus 前端textarea检测：**
- 选择器：`.el-textarea__inner`
- 取值方法：`input_value()`（不是 `text_content()`）

---

### E2E 测试物理拓扑（2026-03-30 修正）

- **Type**: 事实
- **Score**: 0.9
- **Date**: 2026-03-30
- **Status**: Active
---
**测试脚本：** `D:\tis_project\scripts\live_fire_e2e.py`

**关键常量：**
```python
BASE_URL = "http://localhost:3000"
API_URL = "http://localhost:8000"  # Docker backend 直连端口
REAL_PDF = "D:/tis_project/data/test_documents/惠州市交通运输局交通大厦食堂管理和食材配送服务_招标文件.pdf"
SCREENSHOTS_DIR = "D:/tis_project/scripts/screenshots/live_fire"
```

**当前通过率：** 9/11（2 个非阻塞问题：OCR bid_date 未提取、PDF iframe 未加载）

---

### Alembic 迁移链（2026-03-31 最终版）

- **Type**: 事实
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**迁移文件顺序：** `w001` → ... → `w008` → `w009` → `w010` → `w011` → `w012`

| 迁移 | 新增内容 | 涉及表 |
|------|----------|--------|
| `w007` | `relation_identifier`, `differentiation_guidance` | `projects` |
| `w008` | `updated_at` | `approval_logs` |
| `w009` | `is_retender`, `parent_project_id` | `projects` |
| `w010` | `plan_code(String50)`, `agency_project_code(String100)` | `projects` + `tender_documents` |
| `w011` | `is_deleted(Boolean, default=False)` | `projects` |
| `w012` | `ix_projects_is_deleted`, `ix_projects_is_deleted_status` 索引 | `projects` |

**w011 迁移脚本关键片段：**
```python
op.add_column('projects', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default="false"))
op.execute("UPDATE projects SET is_deleted = false WHERE is_deleted IS NULL")
```

**w012 迁移脚本关键片段：**
```python
op.create_index("ix_projects_is_deleted_status", "projects", ["is_deleted", "status"])
op.create_index("ix_projects_is_deleted", "projects", ["is_deleted"])
```

**迁移验证命令：**
```bash
docker compose exec backend alembic current  # 确认：w012
docker compose exec db psql -U postgres -d canteen_system -c "SELECT indexname FROM pg_indexes WHERE tablename='projects' AND indexname LIKE '%is_deleted%'"  # 确认索引
```

---

### 新版 Project / TenderDocument 模型字段（2026-03-31）

- **Type**: 事实
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**Project 模型新增字段：**
```python
plan_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
agency_project_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
is_retender: Mapped[bool] = mapped_column(Boolean, default=False)
parent_project_id: Mapped[Optional[int]] = mapped_column(ForeignKey('projects.id'), nullable=True)
```

**TenderDocument 模型新增字段：**
```python
plan_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
agency_project_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
```

---

### API 端点新增清单（2026-03-31）

- **Type**: 事实
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**`POST /api/projects`（创建项目）— 三重防重校验：**
- 第一关：`plan_code` 精确匹配（排除 discarded / terminated_by_boss）
- 第二关：`agency_project_code` 精确匹配（排除 discarded / terminated_by_boss）
- 第三关：`project_name` 模糊匹配兜底（排除 discarded / terminated_by_boss）
- 409 返回 payload：
```json
{
  "code": "DUPLICATE_TENDER",
  "existing_project_name": "惠州市交通运输局...",
  "duplicate_code": "采购计划编号：441301-2025-03605"
}
```

**`PUT /api/projects/{id}/relationship`（关系标识变更）：**
- 接收：`relationship_flag(bool)`, `differentiation_guidance(string)`
- Week 3+ 变更时触发强制回滚：`status → evaluation_ready`, `generation_mode → null`
- 由 `approval_service.process_relationship_change()` 处理

**`POST /api/projects/{id}/confirm-parsing`（确认表单）— 新增字段：**
```json
{
  "plan_code": "441301-2025-03605",
  "agency_project_code": "HZJJ-2025118号"
}
```

**`POST /api/evaluations/{id}/specialist-approve`（专员审批三动作）：**
```json
{
  "action": "submit_to_boss | direct_execute | terminate",
  "relationship_flag": true,
  "differentiation_guidance": "..."
}
```
- `submit_to_boss` → `pending_boss_approval`
- `direct_execute` → `generating_documents`（越级放行）
- `terminate` → `discarded`

---

### 新版 ProjectStatus / ApprovalAction 枚举（2026-03-31）

- **Type**: 事实
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**ProjectStatus 新增值（app/models/enums.py）：**
```python
PENDING_BOSS_APPROVAL = "pending_boss_approval"  # 专员提交待老板审批
DISCARDED = "discarded"                           # 专员直接终止（不可复活）
```

**ApprovalAction 新增值：**
```python
SPECIALIST_DIRECT_EXECUTE = "specialist_direct_execute"  # 专员越级放行
SPECIALIST_TERMINATE = "specialist_terminate"            # 专员直接终止
```

**状态转换图（新增部分）：**
```
evaluation_ready
    │
    ├──[submit_to_boss]──→ pending_boss_approval
    │                              │
    │                    [boss批准]─┴──→ generating_documents
    │
    ├──[direct_execute]──→ generating_documents  （专员越级）
    │
    └──[terminate]──→ discarded  （不可逆）
```

---

### ConfirmationView 双列网格布局规范（2026-03-31）

- **Type**: 事实
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**UI 规范（强制）：** 所有后台表单默认采用 `el-row/el-col` 紧凑双列布局，拒绝单行铺满。

**ConfirmationView 表单结构：**
```
Row1: 项目名称 [span=24, 全宽]
Row2: 业主单位 [span=24, 全宽]
Row3: 项目预算 [span=12] + 地区 [span=12]
Row4: 项目类型 [span=12] + 截止时间 [span=12]
Row5: 采购计划编号 [span=12] + 采购项目编号 [span=12]
```

**CSS 规范：**
```css
.ocr-form :deep(.el-form-item__label) { font-size: 13px; font-weight: 500; }
.ocr-form :deep(.el-form-item) { margin-bottom: 12px; }
.ocr-form :deep(.el-input__wrapper) { border-radius: 6px; }
```

---

### EvaluationView 渐进式三按钮操作台（2026-03-31）

- **Type**: 事实
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**专员视角操作流程：**
1. 填写"是否有内幕关系"（必选，是/否）
2. 如选择"是"，填写"内幕关系说明"（**选填**，2026-03-31 下午移除10字最低要求）
3. 选择推荐决策（abandon / conditional / worth_bidding）
4. **三按钮操作台**显示：
   - `提交老板审批` → `pending_boss_approval`（Top 图标）
   - `直接执行生成` → `generating_documents`（CaretRight 图标，条件可用）
   - `终止项目` → `discarded`（Close 图标，显示确认对话框）

**Boss 视角：**
- 看到 `pending_boss_approval` 状态的项目
- 同样需填写关系标识 + differentiation_guidance
- 保留定价否决权（pricing_veto）

**强制回滚规则：**
- 关系标识在 Week 3+ 变更 → `status → evaluation_ready` + `generation_mode → null`
- 由 `approval_service.process_relationship_change()` 实现

**初审意见 10 字锁已解除（2026-03-31）：**
- `approval_service.py` 移除了 `override_reason` 最小长度检查
- 现在 `override_reason: Optional` — 初审意见为选填字段

---

### 软删除（is_deleted）项目生命周期（2026-03-31 新增）

- **Type**: 事实
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**软删除逻辑：**
- `DELETE /api/projects/{id}` → `project.is_deleted = True`（非物理删除）
- 软删除项目不参与任何重复检测（三重防重均过滤 `is_deleted=False`）
- 同名项目在软删除后可重新创建（返回 200，不触发 409）

**API 行为：**
- `GET /projects` — 过滤 `is_deleted=False`
- `GET /projects/{id}` — 过滤 `is_deleted=False`
- `POST /projects` 重复检测 — 过滤 `is_deleted=False`
- `DELETE /projects/{id}` — 返回 `{message, project_id, project_name, is_deleted: True}`

**前端 ProjectCard 删除按钮：**
- 悬浮显示（opacity 0 → hover 1）
- `@click.stop` 阻止卡片点击冒泡
- `deleteLock = Set<number>` debounce 防重复提交
- `ElMessageBox.confirm` 确认框：`"确定移入回收站吗？移入后您可以重新上传同名项目。"`
- 删除成功后 `ElMessage.success('已移入回收站，可重新上传同名项目')`
