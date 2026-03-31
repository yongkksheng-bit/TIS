# 因果记录 | 龙虾记忆

> **踩坑记录** - 记录 Bug 及其根本原因，防重复犯错

---

## 记忆卡片格式

每个记忆条目使用以下 YAML 头部：

```yaml
### [记忆条目标题]
- **Type**: 因果
- **Score**: 0.0-1.0
- **Date**: YYYY-MM-DD
- **Status**: Active / Archived
---
```

---

## Bug 与根因记录

### Bug-001：前端 API 双重 `/api` 前缀（2026-03-29）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-29
- **Status**: Active
---
**现象：** 404 Not Found，Docker logs 可见 `/api/api/projects/...`

**根因：** `apiClient` 的 `baseURL = '/api'` 已在 axios 层拼接，前端代码又加了 `/api/` 前缀

**涉及文件：**
| 文件 | 错误写法 | 正确写法 |
|------|----------|----------|
| `ConfirmationView.vue` L167 | `/api/projects/${id}/confirmation-data` | `/projects/${id}/confirmation-data` |
| `ConfirmationView.vue` L209 | `/api/projects/${id}/confirm-parsing` | `/projects/${id}/confirm-parsing` |
| `ProjectUploadView.vue` L106 | `/api/projects` | `/projects` |
| `projectStore.ts` L84 | `/api/projects/${id}` | `/projects/${id}` |
| `TechProposalView.vue` L151 | `/api/v1/projects/...` | `/v1/projects/...` |
| `TechProposalView.vue` L179 | `/api/v1/projects/...` | `/v1/projects/...` |

**诊断命令：**
```bash
# 查 Docker 请求日志中的双重前缀
docker logs tis_backend --tail 100 | grep 'api/api'
```

**修复方式：** 去掉所有前端 Vue/TS 文件中路径里的 `/api` 前缀

---

### Bug-002：`canGenerate` 逻辑错误导致生成按钮假性可用（2026-03-29）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-29
- **Status**: Active
---
**现象：** 生成按钮在未选章节时也被启用（`status === 'generating_documents'`），但点击后无任何反应

**根因：** `TechProposalView.vue` 中 `canGenerate` 使用 OR 逻辑允许"状态=generating_documents 时无需选章节"，但 `generateSection()` 内部对 `!selectedSection.value` 直接 return，UI 欺骗了用户

**错误代码：**
```typescript
// 错误的 OR 逻辑
const canGenerate = computed(() =>
  (selectedSectionId.value !== null || currentProject.value?.status === 'generating_documents')
  && !isGenerating.value
)
```

**正确代码：**
```typescript
// 每个章节必须单独选中才能生成
const canGenerate = computed(() =>
  selectedSectionId.value !== null && !isGenerating.value
)
```

**修复文件：** `TechProposalView.vue` L139

---

### Bug-003：Element Plus textarea 内容检测失败（2026-03-29）

- **Type**: 因果
- **Score**: 0.9
- **Date**: 2026-03-29
- **Status**: Active
---
**现象：** RAG API 200 OK 成功返回内容，但 E2E 测试 `text_content()` 取不到值，报告"No content"

**根因：**
1. Element Plus 的 `el-textarea` 渲染为 `<textarea class="el-textarea__inner">`，不是原生 `<textarea>`
2. Vue v-model 绑定的是 `input_value()`，不是 `textContent`
3. 原 E2E 选择器 `.proposal-content, [class*='content']` 与实际 DOM 结构不匹配

**正确检测方式：**
```python
textarea = page.locator(".el-textarea__inner").first
txt = textarea.input_value()  # 不是 text_content()
```

**修复文件：** `live_fire_e2e.py` L471-487

---

### Bug-005：`qualification_match_score` 伪造 100 分——`else 100` 分支掩盖提取失败（2026-03-30）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-30
- **Status**: Active
---
**现象：** 项目 53 的 `tender_reqs=[]`（TenderDocument 不存在），但 `qualification_match_score=100`，推荐 `worth_bidding`，一切看起来"完美"

**根因：** `qualification_matcher.py` 原逻辑：
```python
if not tender_reqs:       # ← 只有这个条件
    score = 0
else:
    score = int((matched_mandatory / total_mandatory) * 100) if total_mandatory > 0 else 100
# ↑ else 100 在 optional-only 且全未匹配时也返回 100
```

当 `total_mandatory=0` 且 `tender_reqs` 非空但全部是 optional 且全未匹配时，走 `else 100` 分支，粉饰太平。

**修复：** 增加两层检测：
```python
# 检测"标书未解析"场景
if not tender_reqs:
    score = 0
    fatal_missing.append({...SYSTEM_EXTRACTION_FAILED...})

# 检测"optional 要求全未匹配"场景
elif total_mandatory == 0 and matched_optional == 0 and total_optional > 0:
    score = 0
    fatal_missing.append({...SYSTEM_CERT_EXTRACTION_FAILED...})

# 仅在"optional 部分通过"时才给 0~100 分
elif total_mandatory == 0:
    score = int((matched_optional / total_optional) * 100)
```

**修复文件：**
- `qualification_matcher.py` L131-151（增加 matched_optional 计算、两条 fatal 条件）
- `evaluation_engine.py`（增加 `is_extraction_valid` 字段 + `not is_extraction_valid → ABANDON` 推荐分支）

**验证：** `curl http://localhost:8000/api/v1/projects/53/evaluations/generate`
```json
{
  "qualification_match_score": 0,
  "is_qualification_pass": false,
  "is_extraction_valid": false,
  "fatal_risks": [{"cert_code": "SYSTEM_EXTRACTION_FAILED", "reason": "qualification_requirements_not_extracted"}],
  "recommendation": "abandon"
}
```

---

### Bug-006：AxeOS 拦截器脱壳导致深层字段映射丢失（2026-03-29）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-29
- **Status**: Active
---
**现象：** `result.data.report_id` undefined，`d?.qualification?.qualification_match_score` undefined，前端 500 错误

**根因：** `apiClient` 有两个拦截器：
1. **请求拦截器**：`toSnakeCase` 转换 body 字段
2. **响应拦截器**：`toCamelCase(response.data)` 后直接 `return response.data`（不是完整 response）

前端 TypeScript 类型注解错误地把 `result` 标注为 `{data: {...}}`，但实际 `result` 已经是 `data` 的值本身（即 camelCase 后的字典）。

**错误写法：**
```typescript
const result = await apiClient.post(...) as { data: { reportId: number } }
// result 实际是 camelCase 字典，不是 {data: {...}} 包装
qualificationScore.value = result.data?.qualificationMatchScore  // undefined!
```

**正确写法：**
```typescript
const result = await apiClient.post(...) as { code: number; message: string; data: {...} }
const d = result.data
qualificationScore.value = d?.qualification?.qualificationMatchScore ?? 0
```

---

### Bug-004：E2E 测试未选中章节就点生成（2026-03-29）

- **Type**: 因果
- **Score**: 0.9
- **Date**: 2026-03-29
- **Status**: Active
---
**现象：** 生成按钮代码路径正确，API 200 返回内容，但 textarea 始终为空

**根因：** `selectedSectionId` 初始为 `null`，`generateSection()` 在开头 `if (!selectedSection.value) return` 静默退出。API 请求是由 Playwright 触发的但 `section_name` 发送的是 `undefined`

**修复：** Act 3 在找生成按钮之前，先点击 `.el-tree-node__content` 选中章节

---

### Bug-007：端口拓扑混乱——Anaconda 孤儿占 8001，Docker 跑 8000（2026-03-30）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-30
- **Status**: Active
---
**现象：** 调试时始终打到旧代码（假数据 100 分），以为 `docker compose up -d` 已经更新容器，但实际端口 8001 是 Anaconda Python 孤儿进程，8000 才是 Docker backend

**根因链条：**
1. 昨天认为 WSL2 orphan 占 8000 → 在 `.env` 设 `BACKEND_PORT=8001` → Docker 映射 8001
2. 今日发现：8001 是 **Anaconda Python 孤儿进程（PID 28204）**，是之前会话残留的本地 Python uvicorn
3. 8000 才是 Docker backend（`docker compose up -d` 默认端口）
4. 所有 `curl localhost:8001` 打到了 **Windows 本地残留进程**，不是容器内的修复代码

**物理真相：**
```bash
$ docker ps --format "{{.Names}}\t{{.Ports}}"
tis_backend    0.0.0.0:8000->8000/tcp   # Docker 在 8000

$ netstat -ano | grep :8001
TCP    127.0.0.1:8001    0.0.0.0:0    LISTENING    28204
# → Anaconda Python 残留进程，非 Docker
```

**教训：**
- Docker backend 端口由 `.env` 文件中的 `BACKEND_PORT` 决定，不看 `docker ps` 不知道真相
- 端口 8001 在 Windows 上可以是任何进程，不能假设是 Docker
- **唯一可信验证：** `docker ps` 显示的 PORTS 列

**正确做法：** 不再使用 `BACKEND_PORT=8001`，保持 `.env: BACKEND_PORT=8000`，用 `docker compose build backend && docker compose up -d backend` 重建并重启容器。

---

### Env-001：WSL2 Orphan 进程劫持端口 8000（2026-03-25~29，无法根除）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-29（2026-03-30 更新）
- **Status**: Active
---
**更新（2026-03-30）：** 8000 端口实际上 Docker backend 在使用，之前的 WSL2 orphan 进程说法有误。当前 `docker ps` 确认：`tis_backend 0.0.0.0:8000->8000/tcp`。

**现象（原始）：** `localhost:8000` 被 WSL2 内部进程占据

**绕过方案（已修正）：** Docker backend 直连端口 8000，不需要任何映射迁移。

---

### Env-002：Docker 容器重启后网络隔离（2026-03-25）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-25
- **Status**: Active
---
**现象：** `docker compose up -d` 后 backend 无法连接 `host db`，返回 `could not translate host name "db"`

**根因：** Docker Compose 创建的 bridge 网络 `tis_project_tis_net`，在 `docker compose down -v` 重建后，部分容器未正确加入网络

**修复命令：**
```bash
docker network connect tis_project_tis_net tis_backend
docker network connect tis_project_tis_net tis_frontend
```

**健康检查依赖：**
```yaml
depends_on:
  db:
    condition: service_healthy   # 必须等待 PostgreSQL 就绪
```

---

### Bug-008：RAG endpoint 硬编码 MockLLM，绕过 USE_MOCK_LLM 配置（2026-03-31）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**现象：** `USE_MOCK_LLM=false` 和 `DEEPSEEK_API_KEY` 均已正确配置在 `.env` 中，容器内 `echo $USE_MOCK_LLM` 返回 `false`，但 RAG 生成仍返回 `[AUTO MODE RESPONSE]` 模拟内容，`source_chunk_count=0`

**根因：** `rag.py` 第 113 行硬编码直接实例化：
```python
llm = MockDeepSeekLLM()  # ← 绕过了一切环境配置
```
正确的做法是调用 `get_llm()` 工厂函数，它会根据 `USE_MOCK_LLM` 环境变量决定实例化哪个类。

**修复：**
```python
# 错误（硬编码）
llm = MockDeepSeekLLM()

# 正确（工厂模式）
llm = get_llm()  # respects USE_MOCK_LLM env var
```

**教训：** 即使 env var 正确配置了，如果代码直接 `new` 具体类而不是通过工厂，env var 形同虚设。工厂模式是唯一可靠的配置注入方式。

**二次修复（Import 遗漏）：** 修复 `MockDeepSeekLLM()` 后，忘了同步更新 import 语句，导致 `NameError: name 'get_llm' is not defined`。正确做法是一开始就不要 import 具体类，只 import 工厂函数。

**修复后 import：**
```python
# 错误（直接 import 具体类）
from app.core.week3_rag.llm_mock import MockDeepSeekLLM
llm = MockDeepSeekLLM()  # 绕过环境配置

# 正确（import 工厂函数）
from app.core.week3_rag.llm_mock import get_llm
llm = get_llm()  # 遵守 USE_MOCK_LLM 配置
```

---

### 模式：Element Plus 组件自动化三要素（2026-03-29）

- **Type**: 模式
- **Score**: 0.9
- **Date**: 2026-03-29
- **Status**: Active
---
**发现背景：** 上传组件、Radio 组件都在 Playwright 测试中遇到交互问题

**Element Plus 组件三要素：**
1. **隐藏真实输入**：原生 `<input type="file">` 或 `<input type="radio">` 被藏在组件内部，需用 `.el-upload__input` 或 `input[type="radio"]` 定位
2. **Vue 响应式需事件冒泡**：`.click()` 直接点在组件 DOM 上不会触发 Vue 响应，需 `label.dispatchEvent(new MouseEvent('click', {bubbles:true}))`
3. **上传完成需等待**：文件上传后 backend OCR 解析有延迟，需显式 `wait_for_timeout()`

**已验证的 Playwright 策略：**
```python
# 文件上传
file_input = page.locator('.el-upload__input')
file_input.set_input_files(PDF_PATH)

# Radio 按钮
label = page.locator('.el-radio__label', has_text='是').first
label.dispatchEvent(new MouseEvent('click', {bubbles: True, cancelable: True}))
```

---

### 因果链-001：5432 端口撞车 → "借壳挂载"成为标准（2026-03-25~31）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**初始事件：** 本地开发机 5432 端口已被其他 PostgreSQL 实例占用，导致 Docker 的 `tis_db` 容器无法将 5432 直接映射到物理机。

**解决方案（"借壳挂载"）：**
- Docker Compose 将容器内 5432 映射到物理机 **5433**（而不是 5432）
- 外部连接字符串改为 `localhost:5433`
- 内部（容器间）仍用 `db:5432`

**因果链条：**
```
物理机 5432 被占用（2026-03-25）
  → Docker Compose 映射到 5433（2026-03-25）
    → 外部连接统一用 5433（2026-03-25）
      → AI_MEMORY.md 记录为"Docker 5432 / 物理 5433"（固化）
        → 2026-03-30 发现：物理 5432 其实是 canteen_system 数据库的直接连接（原有系统遗产）
          → 结论：两个数据库都在用，端口撞车是历史共处状态，不是错误
```

**关键事实：**
- `tis_db`（Docker PostgreSQL + pgvector）：`localhost:5433` → `container:5432`
- 物理 5432：可能是宿主的另一个 PostgreSQL（`canteen_system` 的原始实例）
- 两者共用数据库名 `canteen_system`，但实际是两个独立实例

**教训：** 端口撞车不一定是错误，也可能是两个合法服务共存。"借壳挂载"是工程妥协，不是 Bug。

---

### 因果链-002：业务方复盘 → 双重防重 + Week 1/2 重构（2026-03-31）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**触发事件：** 业务方提供真实招标文件样本，发现仅用 `project_name` 防重存在严重漏洞：
- 同一业主的同一项目，每次招标都有不同的项目名称（如 "食堂配送服务 2025 第一批" vs "食堂配送服务 2025 第二批"）
- 真实业务标识是 **采购计划编号（plan_code）** 和 **采购项目编号（agency_project_code）**

**因果链条：**
```
业务方提供真实样本（2026-03-31 上午）
  → 发现仅靠 project_name 无法防止重复投标
    → 增加 plan_code + agency_project_code 模型字段（w010 迁移）
      → parser.py 增加正则提取逻辑（采购计划编号、采购项目编号）
        → projects.py 增加三重校验（plan_code → agency_project_code → project_name）
          → 409 Payload 增加 duplicate_code 字段（含编号类型标识）
```

**新增文件：**
- `alembic/versions/w010_add_plan_codes.py` — plan_code + agency_project_code
- `app/core/week1_document/parser.py` — regex 提取采购计划编号（格式：`441301-2025-03605`）和采购项目编号（格式：`HZJJ-2025118号`）

---

### 因果链-003：业务方深度复盘 → 关系标识位置 + 专员越级权力（2026-03-31）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**触发事件：** 业务方评审 Week 1/2 工作流，发现两个问题：
1. `relationship_flag` 在 Week 1（ConfirmationView）填写太早，应在 Week 2 评估时由专员和老板共同确认
2. 高级专员应有权跳过老板直接放行生成，不需要每次都走老板审批流程

**因果链条：**
```
业务方评审（2026-03-31 下午）
  → relationship_flag 从 Week 1 移到 Week 2（ConfirmationView 删除，EvaluationView 新增）
    → Week 2 需同时满足：专员 view + boss view 都填写关系标识
      → 增加强制回滚机制（Week 3+ 变更 → evaluation_ready）
        → 增加专员越级放行（direct_execute → generating_documents）
          → 3 动作模型：submit_to_boss / direct_execute / terminate
            → 新增状态：pending_boss_approval / discarded
```

**涉及文件：**
- `ConfirmationView.vue` — 删除 relation_identifier + differentiation_guidance
- `EvaluationView.vue` — 新增 3 按钮操作台 + 关系标识表单
- `approval_service.py` — 新增 process_relationship_change() 方法
- `projects.py` — 新增 PUT /{id}/relationship 端点
- `enums.py` — 新增 PENDING_BOSS_APPROVAL / DISCARDED / SPECIALIST_DIRECT_EXECUTE / SPECIALIST_TERMINATE

---

### 因果链-004：ElMessage.error 阻断失效 → 必须升级为 ElMessageBox.confirm（2026-03-31）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**触发事件：** 业务方复盘发现，409 冲突时使用 `ElMessage.error()` 弹窗，用户可能忽略提示直接关闭，导致重复投标。

**根因：** `ElMessage.error()` 是非阻断性提示，用户可以不理会继续操作。

**解决方案：** 所有业务阻断（409 冲突、权限不足、状态不允许）统一使用 `ElMessageBox.confirm()`，提供明确的双向决策按钮。

**涉及文件：**
- `ProjectUploadView.vue` — 409 处理从 `ElMessage.error()` 升级为 `ElMessageBox.confirm()`
- 升级后弹窗文案：`"检测到系统已存在该项目：【${existingName}】${dupMsg}。如果这是流标后的重新招标，请点击【确认作为二次投标】放行上传。"`

**规范（已固化到 AI_MEMORY.md）：**
- `ElMessage.error()` → 仅用于非阻断性错误（临时提示）
- `ElMessageBox.confirm()` → 所有需要用户主动决策的业务阻断

---

### Bug-009：OOM 崩溃导致 Docker 构建中断 → Transformers 与 torch 2.1.0 版本冲突（2026-03-31）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**现象：** `tis_ai_service` 启动失败，`AttributeError: module 'torch.utils._pytree' has no attribute 'register_pytree_node'`

**因果链条：**
```
Docker 构建 ai_service 镜像（耗时 1421s，1360MB）
  → 系统内存压力过大
    → OOM Killer 触发，强制关闭 Claude Code 窗口
      → 用户重启后重试
        → tis_ai_service 启动时报 transformers/torch 版本不兼容
          → transformers>4.38.0 使用了 torch.utils._pytree.register_pytree_node
            → torch 2.1.0 没有此 API
```

**根因：** `transformers` 最新版本依赖 `torch.utils._pytree.register_pytree_node`，该 API 在 torch 2.1.0 中不存在。`sentence-transformers==2.7.0` 间接拉取了过高的 transformers 版本。

**修复：**
1. `ai_service/requirements.txt` 锁定 `transformers<=4.38.0`
2. `ai_service/main.py` 顶部加 `os.environ["TOKENIZERS_PARALLELISM"] = "false"` 增强稳定性
3. 重建镜像：`docker compose build tis_ai_service && docker compose up -d tis_ai_service`

**教训：** 大模型镜像构建耗时长、内存占用大，应在 `.env` 或 `docker-compose.yml` 中预先锁定所有依赖版本，避免构建完成后才发现兼容性问题。

---

### Bug-010：SentenceTransformer 不支持 `cache_dir` 参数 → TypeError 启动死循环（2026-03-31）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**现象：** `tis_ai_service` 启动后报 `TypeError: __init__() got an unexpected keyword argument 'cache_dir'`，陷入死循环无法正常加载模型。

**根因：** `SentenceTransformer` 和 `CrossEncoder` 的构造函数根本不接受 `cache_dir` 参数——这是错误地将其与 HuggingFace `transformers` 的 `AutoModel` API 混淆了。模型缓存路径由环境变量 `HF_HOME` 控制，应在 Docker 环境变量中设置，而非代码中传递。

**错误代码：**
```python
cache_dir = os.environ.get("HF_HOME", "/tmp/huggingface")
embedder = SentenceTransformer(EMBEDDER_MODEL, cache_dir=cache_dir)   # ← TypeError
reranker = CrossEncoder(RERANKER_MODEL, cache_dir=cache_dir)           # ← TypeError
```

**正确代码：**
```python
embedder = SentenceTransformer(EMBEDDER_MODEL)   # HF_HOME 通过 env var 控制
reranker = CrossEncoder(RERANKER_MODEL)           # 同上
```

**修复文件：** `ai_service/main.py` — 删除 `cache_dir` 变量及所有 `cache_dir=` 实参

**教训：** `sentence-transformers` 的 `SentenceTransformer` 与 `transformers` 的 `AutoModel` API 并不完全一致，缓存机制依靠环境变量而非构造函数参数。

---

### 因果链-005：RTX 3060 6GB OOM → GPU+CPU 异构计算架构（2026-03-31）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**触发事件：** RTX 3060（6GB）显存无法同时容纳 BGE-Small Embedder + BGE-Reranker-Base 两个模型的全量参数，导致 `tis_ai_service` 启动时 OOM。

**架构决策：** 采用 GPU + CPU 异构计算，显存专供 Embedder，CPU 承担 Reranker 精排任务。

**因果链条：**
```
RTX 3060 6GB 无法双模全显（2026-03-31）
  → BAAI 官方无 bge-reranker-small 模型可用
    → Embedder 保留 GPU FP16（高吞吐向量检索）
      → Reranker 迁移至 CPU FP32（全精度交叉编码精排）
        → OOM 问题解除，异构架构稳定运行
```

**最终部署模式：**
| 模型 | 设备 | 精度 | 职责 |
|------|------|------|------|
| BGE-Small (bge-small-zh-v1.5) | GPU (cuda) | FP16 | 向量嵌入生成 |
| BGE-Reranker-Base | CPU | FP32 | 交叉编码精排 |

**关键约束：** CPU 推理必须移除 `.half()`，PyTorch CPU 不完全兼容 float16 算子，强制 FP32 是唯一安全路径。

**涉及文件：** `ai_service/main.py` lifespan 函数

---

### Bug-011：DeepSeekEmbedder 错误调用外部嵌入 API → 架构根本性违规（2026-03-31）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**现象：** `curl -X POST http://localhost:8000/api/v1/projects/81/generate-section` 返回 `{"detail":"Generation failed: DeepSeek embedding API error 404: "}`

**根因：** `embedder.py` 中的 `DeepSeekEmbedder` 调用 `https://api.deepseek.com/embeddings`，完全违背架构设计：

```
架构设计：
  Embedding/Reranking → 本地 tis_ai_service (BGE 模型) → http://ai_service:8000/embed
  Text Generation    → DeepSeek Chat API              → https://api.deepseek.com/chat/completions

实际错误实现：
  Embedding → DeepSeek Embeddings API (deepseek-embedder) ← 根本性错误！
```

**错误代码：**
```python
class DeepSeekEmbedder(BaseEmbedder):
    BASE_URL = "https://api.deepseek.com"  # ← 错误！Embedding 不走外部 API
    def _call_embedding_api(self, texts):
        url = f"{self.BASE_URL}/embeddings"  # ← 404/无效模型
        ...
```

**正确代码：**
```python
class AIServiceEmbedder(BaseEmbedder):
    """本地 AI 微服务：BGE-Small (GPU) + BGE-Reranker-Base (CPU)"""
    BASE_URL = "http://ai_service:8000"  # ← Docker 内部网络地址

    def _call_embed_api(self, texts):
        url = f"{self.BASE_URL}/embed"  # ← 本地 BGE 模型向量生成
        ...
```

**修复文件：** `app/core/week3_rag/embedder.py`
- 删除 `DeepSeekEmbedder` 类（调用外部嵌入 API 的错误实现）
- 新增 `AIServiceEmbedder` 类（调用本地 `http://ai_service:8000/embed`）
- `create_embedder()` 工厂：`USE_MOCK_EMBEDDER=true` → `MockEmbedder`，否则 → `AIServiceEmbedder`
- DeepSeek API 调用仅保留在 `llm_mock.py:RealDeepSeekLLM.generate()`（chat/completions 端点）

**架构黄金法则（永久固化）：**
- **Embedding / Reranking**：只允许调用本地 `ai_service:8000`，绝不调用任何外部厂商嵌入 API
- **Text Generation**：只允许调用 DeepSeek `/chat/completions`，绝不用于嵌入任务
- `USE_MOCK_EMBEDDER=true` → `MockEmbedder`（纯本地 deterministic mock）
- `USE_MOCK_EMBEDDER=false` → `AIServiceEmbedder`（本地 BGE 模型）

---

### 因果链-006：软删除 + 三重防重 is_deleted 集成（2026-03-31 下午）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**触发事件：** 用户在 Dashboard 上传同名项目后无法重新创建——项目被物理删除后，同名检测仍然存在。

**因果链条：**
```
业务方测试：上传"测试项目" → 物理删除 → 重新上传同名项目 → 409 Conflict
  → 根因：物理删除不改变数据库记录，项目名重复检测仍触发
    → 业务方需求：删除的项目应该不参与重复检测，允许同名重建
      → 引入 is_deleted 软删除字段（Boolean, default=False）
        → w011 迁移添加 is_deleted 列
        → w012 迁移添加 is_deleted + status 复合索引
          → DELETE 端点设置 is_deleted=True，不物理删除
            → 三重防重（plan_code / agency_project_code / project_name）全部加 is_deleted=False 过滤
              → 软删除项目不阻塞同名重建
```

**E2E 验证结果（2026-03-31）：**
```
创建项目 ID:85 → 删除 → is_deleted=True → 重建同名 → ID:86 (200 OK)
```

---

### Bug-012：初筛意见10字锁导致专员无法直接执行（2026-03-31 下午）

- **Type**: 因果
- **Score**: 1.0
- **Date**: 2026-03-31
- **Status**: Active
---
**现象：** 专员选择 `direct_execute` 并填写 override_reason 为"通过"（2字），API 返回 400 错误"初审意见至少10字符"。

**根因：** `approval_service.py` 中对 `override_reason` 设置了硬性最小长度检查：
```python
if not override_reason or len(override_reason) < 10:
    raise ValueError(f"Approval of project with fatal_risks requires override_reason >= 10 chars")
```

**修复：** 移除长度检查，`override_reason` 改为 Optional[str]：
```python
# 修复前
if not override_reason or len(override_reason) < 10:
    raise ValueError(...)

# 修复后：override_reason 完全选填，不做长度限制
```

**教训：** 初审意见是"意见记录"而非"正式审批文档"，强制10字无业务依据。防呆设计不应演变为用户体验阻碍。
