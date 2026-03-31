# 模式记录 | 龙虾记忆

> **最佳实践** - 验证成功的代码片段、模板、设计模式

---

## 记忆卡片格式

每个记忆条目使用以下 YAML 头部：

```yaml
### [记忆条目标题]
- **Type**: 模式
- **Score**: 0.0-1.0
- **Date**: YYYY-MM-DD
- **Status**: Active / Archived
---
```

---

## 最佳实践与代码模板

### 模式-001：业务阻断弹窗模式（ElMessageBox.confirm + Force Retry）

- **Type**: 模式
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**适用场景：** 409 项目重名、权限不足、状态不允许等所有需要用户主动决策的业务阻断

**前端实现模板（ProjectUploadView.vue）：**
```javascript
import { ElMessageBox } from 'element-plus'

async function handleCreateProject(payload) {
  try {
    await apiClient.post('/projects', payload)
    ElMessage.success('项目创建成功')
    router.push('/projects')
  } catch (err) {
    if (err?.response?.status === 409) {
      const detail = err.response.data.detail
      const existingName = detail.existing_project_name ?? ''
      const dupMsg = detail.duplicate_code ? `(${detail.duplicate_code})` : ''

      const confirmed = await ElMessageBox.confirm(
        `检测到系统已存在该项目：【${existingName}】${dupMsg}。\n\n` +
        `如果这是流标后的重新招标，请点击【确认作为二次投标】放行上传。`,
        '项目重复 — 二次投标确认',
        {
          confirmButtonText: '确认作为二次投标',
          cancelButtonText: '取消',
          type: 'warning',
          center: true,
        }
      )

      if (confirmed === 'confirm') {
        await apiClient.post('/projects', { ...payload, force_retender: true })
        ElMessage.success('二次投标项目创建成功')
        router.push('/projects')
      }
    } else {
      ElMessage.error('创建失败：' + (err.message ?? String(err)))
    }
  }
}
```

**关键要素：**
1. `center: true` — 居中显示，提升视觉权重
2. `type: 'warning'` — 橙色警告，符合业务阻断语义
3. 确认后用 `force_retender=true` 重新发起请求
4. 取消时静默返回，不报错，不刷新页面

---

### 模式-002：紧凑双列表格布局模式（el-row/el-col Compact Grid）

- **Type**: 模式
- **Score**: 0.95
- **Date**: 2026-03-31
- **Status**: Active
---
**适用场景：** 所有 Element Plus 后台管理表单，默认采用紧凑双列网格，拒绝单行铺满

**布局模板（ConfirmationView.vue 结构）：**
```html
<el-card class="form-card">
  <el-form :model="formData" label-position="top" class="ocr-form">

    <!-- Row 1: 全宽字段 -->
    <el-row :gutter="12">
      <el-col :span="24">
        <el-form-item label="项目名称" class="compact-label">
          <el-input v-model="formData.project_name" />
        </el-form-item>
      </el-col>
    </el-row>

    <!-- Row 2: 全宽字段 -->
    <el-row :gutter="12">
      <el-col :span="24">
        <el-form-item label="业主单位" class="compact-label">
          <el-input v-model="formData.owner_unit" />
        </el-form-item>
      </el-col>
    </el-row>

    <!-- Row 3: 双列并排 -->
    <el-row :gutter="12">
      <el-col :span="12">
        <el-form-item label="项目预算（元）" class="compact-label">
          <el-input-number v-model="formData.budget_amount" ... />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="地区" class="compact-label">
          <el-input v-model="formData.region" />
        </el-form-item>
      </el-col>
    </el-row>

    <!-- Row 4: 双列并排 -->
    <el-row :gutter="12">
      <el-col :span="12">
        <el-form-item label="项目类型" class="compact-label">
          <el-select v-model="formData.project_type" ... />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="提交投标文件截止时间" class="compact-label">
          <el-date-picker v-model="formData.bid_open_date" ... />
        </el-form-item>
      </el-col>
    </el-row>

    <!-- Row 5: 双列并排 -->
    <el-row :gutter="12">
      <el-col :span="12">
        <el-form-item label="采购计划编号" class="compact-label">
          <el-input v-model="formData.plan_code" ... />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="采购项目编号（选填）" class="compact-label">
          <el-input v-model="formData.agency_project_code" ... />
        </el-form-item>
      </el-col>
    </el-row>

  </el-form>
</el-card>
```

**配套 CSS 规范：**
```css
.ocr-form :deep(.el-form-item__label) {
  font-weight: 500;
  font-size: 13px;
  margin-bottom: 2px !important;
}
.ocr-form :deep(.el-form-item) {
  margin-bottom: 12px;
}
.ocr-form :deep(.el-input__wrapper),
.ocr-form :deep(.el-select__wrapper) {
  border-radius: 6px;
}
```

**布局原则：**
- `gutter="12"` — 两列间距 12px
- `label-position="top"` — 标签在输入框上方（节省横向空间）
- 配对字段（预算+地区、类型+日期）放同一行
- 非配对字段（项目名称、业主单位）各占一整行

---

### 模式-003：三重防重校验 API 模式（Triple-tier Deduplication）

- **Type**: 模式
- **Score**: 0.9
- **Date**: 2026-03-31
- **Status**: Active
---
**适用场景：** `POST /api/projects` 创建项目端点的防重校验

**后端实现模板（projects.py）：**
```python
from app.models.enums import ProjectStatus

ACTIVE_STATUSES = {
    ProjectStatus.UPLOADED, ProjectStatus.PARSING,
    ProjectStatus.EVALUATION_READY, ProjectStatus.PENDING_BOSS_APPROVAL,
    ProjectStatus.APPROVED_BY_SPECIALIST, ProjectStatus.GENERATING_DOCUMENTS,
    ProjectStatus.DOCUMENTS_GENERATED, ProjectStatus.PRICING_PENDING,
    ProjectStatus.PRICING_COMPLETED, ProjectStatus.COMPLETED,
}
RETIRED_STATUSES = {ProjectStatus.DISCARDED, ProjectStatus.TERMINATED_BY_BOSS}


def _check_duplicate(db: Session, project_name: str, plan_code: str | None,
                     agency_project_code: str | None) -> tuple[bool, dict]:
    """三重防重校验，返回 (is_duplicate, conflict_detail)"""
    q = db.query(Project).filter(
        Project.status.notin_(RETIRED_STATUSES)
    )

    # 第一关：plan_code 精确匹配
    if plan_code:
        existing = q.filter(Project.plan_code == plan_code).first()
        if existing:
            return True, {
                "existing_project_name": existing.project_name,
                "duplicate_code": f"采购计划编号：{plan_code}",
                "existing_status": existing.status,
            }

    # 第二关：agency_project_code 精确匹配
    if agency_project_code:
        existing = q.filter(Project.agency_project_code == agency_project_code).first()
        if existing:
            return True, {
                "existing_project_name": existing.project_name,
                "duplicate_code": f"采购项目编号：{agency_project_code}",
                "existing_status": existing.status,
            }

    # 第三关：project_name 兜底匹配
    existing = q.filter(Project.project_name == project_name).first()
    if existing:
        return True, {
            "existing_project_name": existing.project_name,
            "duplicate_code": None,
            "existing_status": existing.status,
        }

    return False, {}
```

**409 响应体规范：**
```json
{
  "code": "DUPLICATE_TENDER",
  "message": "系统已存在相同项目",
  "existing_project_name": "惠州市交通运输局食堂配送服务",
  "duplicate_code": "采购计划编号：441301-2025-03605",
  "existing_status": "generating_documents"
}
```

**关键设计点：**
1. 校验顺序不可颠倒（plan_code > agency_project_code > project_name）
2. `discarded` 和 `terminated_by_boss` 必须排除
3. `duplicate_code` 必须包含编号类型中文前缀，供前端拼接友好文案
4. 即使 `force_retender=true`，plan_code 重复仍应返回 409（因为是同一标的的二次投标，不允许）

---

### 模式-004：项目软删除 + 回收站重建模式（Soft Delete + Re-creation）

- **Type**: 模式
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**适用场景：** 项目列表删除、回收站管理、同名项目重写

**后端实现模板（projects.py DELETE 端点）：**
```python
@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """软删除：设置 is_deleted=True。硬删除扩展点见 approval_service._hard_delete_project()。"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.is_deleted == False,
    ).first()
    if not project:
        raise HTTPException(404, "Project not found")
    project.is_deleted = True
    db.commit()
    return {
        "message": "项目已移入回收站",
        "project_id": project_id,
        "project_name": project.project_name,
        "is_deleted": True,
    }
```

**三重防重均过滤 is_deleted=False（projects.py 创建端点）：**
```python
db.query(Project).filter(...).filter(Project.is_deleted == False).first()
```

**前端实现模板（ProjectCard.vue + DashboardView.vue）：**
```typescript
// ProjectCard.vue — 删除按钮（悬浮显示）
<el-button class="delete-btn" type="danger" :icon="Delete" circle size="small" text
           @click.stop="emit('delete', project)" />
<style>
.delete-btn { position: absolute; top: 8px; right: 8px; opacity: 0; transition: opacity 0.2s; }
.project-card:hover .delete-btn { opacity: 1; }
</style>

// DashboardView.vue — handleDelete with debounce
const deleteLock = new Set<number>()
async function handleDelete(project: Project) {
  if (deleteLock.has(project.id)) return
  deleteLock.add(project.id)
  try {
    await ElMessageBox.confirm(
      `确定移入回收站吗？移入后您可以重新上传同名项目。`,
      '移入回收站',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning', center: true }
    )
    await apiClient.delete(`/projects/${project.id}`)
    ElMessage.success('已移入回收站，可重新上传同名项目')
    await projectStore.fetchProjects(authStore.currentUser.role)
  } catch { /* silently ignore */ }
  finally { deleteLock.delete(project.id) }
}
```

**关键设计点：**
1. `is_deleted=False` 过滤是所有查询的默认条件
2. 删除成功后立即刷新列表（`fetchProjects`）
3. debounce `deleteLock = Set<number>` 防止快速重复点击
4. `@click.stop` 阻止卡片点击事件冒泡到父级

