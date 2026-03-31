# 架构决策 | 龙虾记忆

> **永久保护 (Pinned)** - 架构选型、业务硬规则、Prompt策略

---

## 系统级规则（必须严格遵守）

### 规则 1：架构决策记录
任何架构选型、业务逻辑硬性约束，**必须**记录在此文件。

### 规则 2：Bug根因记录
任何解决过的复杂 Bug 及其根本原因，**必须**记录在 `02_CAUSALITY.md`。

### 规则 3：记忆卡片元数据
写入记忆时必须使用 YAML 头部格式：
```yaml
- **Type**: 决策/因果/模式/事实
- **Score**: 0.0-1.0 (0.9-1.0 永久保护，0.5-0.8 长期参考，<0.5 临时记录)
- **Date**: YYYY-MM-DD
- **Status**: Active / Archived
```

### 规则 4：状态更新
每次完成阶段性任务或每天下班前，**必须**主动更新 `00_SYSTEM_STATUS.md`。

---

## 决策记录

### 决策-001：关系标识与生成模式正交解耦（ARCH-DECOUPLE）

- **Type**: 决策
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**问题背景：**
最初设计认为 `relationship_flag=true` 的项目应强制走 GUIDED 生成模式，理由是"有内幕关系的项目需要专员精细化编辑"。这是一个错误的耦合推导。

**决策内容：**
`relationship_flag`（业务关系标识）和 `generation_mode`（AI 生成模式）属于完全独立的不同维度，互不决定对方：

| 关系标识 \ 生成模式 | AUTO | GUIDED |
|---------------------|------|--------|
| 有内幕关系 | ✅ 合理（简单项目） | ✅ 合理（复杂项目） |
| 无内幕关系 | ✅ 合理（简单项目） | ✅ 合理（复杂项目） |

**业务理由：**
- 关系标识决定的是"投标策略风险"，与"技术标内容的生成方式"无逻辑关联
- 专员应根据项目复杂度（章节数、定制化需求）独立选择生成模式
- 两者耦合会导致简单有关系项目被强制进入繁琐的 GUIDED 流程，降低效率

**实施要点：**
- 前端 EvaluationView 的 relationship_flag 和 generation_mode 是两个独立选择器
- 后端 `approval_service.py` 中两者分别处理，不存在因果推导
- Week 3+ 变更 relationship_flag 仅触发状态回滚，不影响 generation_mode

** архитектурный违反惩罚：** 若发现代码中有 `if relationship_flag: generation_mode = 'guided'"`，立即作为 Bug 记录。

---

### 决策-002：真实业务编号优先于项目名称（双重防重键体系）

- **Type**: 决策
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**问题背景：**
仅用 `project_name` 作为项目防重的依据存在严重漏洞：
- 同一业主的同一项目，每次招标名称都不同（如"食堂配送服务 2025 第一批" vs "食堂配送服务 2025 第二批"）
- 业务方提供真实标书后发现，真实世界中的精确标识是 **采购计划编号**（plan_code）和 **采购项目编号**（agency_project_code）

**决策内容：**
防重校验必须严格按以下优先级执行：

```
第一优先级：plan_code（采购计划编号）精确匹配
    ↓ 不存在或为空
第二优先级：agency_project_code（采购项目编号）精确匹配
    ↓ 不存在或为空
第三优先级：project_name（项目名称）模糊匹配（兜底）
```

**废弃状态排除：**
`discarded`（专员终止）和 `terminated_by_boss`（老板否决）状态的项目不参与重复检测，因为这些是项目的"死亡状态"，重新招标是合法行为。

**编号格式规范：**
- `plan_code` 格式：`441301-2025-03605`（行政区划-年份-序号）
- `agency_project_code` 格式：`HZJJ-2025118号`（代理机构缩写-年份-序号+号）

**违反惩罚：**
若发现防重接口仅用 `project_name` 做唯一校验而不校验 plan_code，立即作为 P0 Bug 记录。

---

### 决策-003：业务阻断强制使用 ElMessageBox.confirm（交互安全规范）

- **Type**: 决策
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**问题背景：**
最初使用 `ElMessage.error()` 拦截 409 冲突（项目重名）。但 `ElMessage.error()` 是非阻断性提示：用户可以忽略红色提示条直接关闭，继续操作导致重复投标，业务方复盘后认定这是高风险设计。

**决策内容：**
所有需要用户**主动决策**的业务阻断场景，统一使用 `ElMessageBox.confirm()` 提供居中闭环弹窗：

| 场景 | 组件选择 | 理由 |
|------|----------|------|
| 409 项目重名 | `ElMessageBox.confirm` | 需要用户决定是否强制新建 |
| 权限不足 | `ElMessageBox.confirm` | 需要用户确认或取消操作 |
| 状态不允许操作 | `ElMessageBox.confirm` | 需要用户决策是否强制继续 |
| 临时性错误提示 | `ElMessage.error` | 非阻断，告知即可 |

**ElMessageBox.confirm 必填参数：**
```javascript
await ElMessageBox.confirm(message, title, {
  confirmButtonText: '确认XXX',
  cancelButtonText: '取消',
  type: 'warning',      // 或 'danger'/'info'
  center: true,          // 居中显示
})
```

**ElMessage.error 适用范围：**
- 表单验证失败（字段格式错误等）
- 网络错误提示
- 操作成功后的非关键提示

---

### 决策-004：专员渐进式三动作权力模型（Specialist 3-Action Authority）

- **Type**: 决策
- **Score**: 0.95
- **Date**: 2026-03-31
- **Status**: Active
---
**问题背景：**
最初设计采用严格的线性审批流：专员提交 → Boss 审批 → 生成。无论项目大小都要走 Boss 审批，导致简单项目审批效率低下，高级专员缺乏自主决策空间。

**决策内容：**
专员拥有三个渐进式操作选项，而非单一提交按钮：

```
[提交老板审批]  → pending_boss_approval  （标准流程，等待Boss决策）
      ↓
[直接执行生成]  → generating_documents   （越级放行，Boss仅在定价环节保留否决权）
      ↓
[终止项目]     → discarded              （不可逆，需二次确认）
```

**各动作的业务语义：**
- `submit_to_boss`：常规项目，金额大或复杂，需要 Boss 知情
- `direct_execute`：简单项目（服务类、金额≤50万），专员判断风险可控，直接进入生成
- `terminate`：专员判断不值得投标，直接废弃

**Boss 的定价否决权（保留）：**
即使专员走了 `direct_execute`，Boss 在 Week 4（定价）环节仍可行使否决权。这确保了越级放行不会绕过最终财务控制。

**与 RBAC 的关系：**
- 专员 + `direct_execute` → 自己承担决策责任
- Boss + 审批 → 承担监督责任
- 两者分离，不互相阻塞

---

### 决策-005：项目软删除（Soft Delete）优先于物理删除

- **Type**: 决策
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**问题背景：**
最初的 DELETE 操作是物理删除，导致同名项目无法重新创建。同时物理删除在商业 SaaS 场景下存在数据安全风险（误删无法恢复、审计追溯丢失）。

**决策内容：**
所有项目删除统一采用软删除模式：
- `DELETE /api/projects/{id}` → `is_deleted = True`，数据保留在数据库
- 软删除项目**不参与**任何重复检测查询（plan_code / agency_project_code / project_name 三重关卡均过滤 `is_deleted=False`）
- 允许同名项目在软删除后重新创建（返回 200，不触发 409）
- 前端 ProjectCard 删除按钮提供明确的 `ElMessageBox.confirm` 确认框

**is_deleted 查询过滤规则：**
```python
# 列表查询
db.query(Project).filter(Project.is_deleted == False)

# 详情查询
db.query(Project).filter(Project.id == project_id, Project.is_deleted == False)

# 重复检测（三重关卡均加）
db.query(Project).filter(...).filter(Project.is_deleted == False)
```

**硬删除预留钩子：**
未来扩展物理删除时，必须：
1. 先将项目数据归档至审计表
2. 删除 TenderDocument / BidDocument / DocumentImage 等关联数据
3. 清理 MinIO/S3 对象存储中的文件
4. 记录不可篡改的审计日志

---

### 决策-006：RAG 4维度法务级资质提取（替代简单 OCR 关键词匹配）

- **Type**: 决策
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**问题背景：**
早期资质提取采用简单关键词匹配（`if '小微企业' in text`），存在严重漏检风险：PDF 排版导致关键词被拆分、变体表达无法识别、图片型 PDF 完全失效。

**决策内容：**
RAG 资质提取采用 4 维度法务级 Prompt（`qualification_extractor.py`）：
```
维度1【基础法定资质】：提取《政府采购法》第二十二条要求的所有资质
维度2【项目特定资格】：提取所有行业特许证明（食品/卫生/特种设备等）
维度3【实质性条款】：标注★/必须级别的资格性审查条款
维度4【终极校验】：对照招标文件"资格性审查表"交叉验证
```

**长文档截断策略：**
- 超过 12,000 字符的文档在 RAG 检索前截断
- 12,000 字符是 BGE-Small（512维）向量化的最优分块节点
- RAG 检索是处理长文档的唯一路径

**输出格式：**
```json
{
  "qualifications": [
    {
      "cert_code": "FOOD_OPERATION_LICENSE",
      "title": "食品经营许可证",
      "matched": true,
      "type": "实质性"
    }
  ],
  "is_military_procurement": false
}
```

**绝对禁止：**
- 严禁将 OCR 直接提取结果作为资质判断的唯一依据
- 严禁在 OCR 阶段做业务有效性判断（Week 1 只认客观事实）

