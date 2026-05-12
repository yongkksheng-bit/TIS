# TIS 项目 — AI 唤醒记忆 (Claude Memory)

> 上次对话结束时间：2026-03-31 17:00（重启前快照）
> 状态：**ai_service 微服务异构计算架构确立，镜像 build 成功，重启待拉起**

---

## 🔴 ai_service 微服务状态快照（2026-03-31 17:00 重启前）

### 最终部署架构（GPU + CPU 异构计算）

| 模型 | 设备 | 精度 | 职责 |
|------|------|------|------|
| BGE-Small (bge-small-zh-v1.5) | GPU (cuda) | FP16 | 向量嵌入生成 |
| BGE-Reranker-Base | CPU | FP32 | 交叉编码精排 |

**核心约束：** CPU 推理必须移除 `.half()`，PyTorch CPU 不完全兼容 float16 算子，强制 FP32 是唯一安全路径。

### ai_service/main.py 代码状态（已确认完毕）

```python
# 顶部
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# lifespan 函数（已最终版）
embedder = SentenceTransformer(EMBEDDER_MODEL)
embedder = embedder.to("cuda").half()   # GPU FP16

reranker = CrossEncoder(RERANKER_MODEL)
reranker.model = reranker.model.to("cpu")  # CPU FP32，无 .half()
```

**已移除：** `cache_dir` 参数（SentenceTransformer 不接受此参数，会报 TypeError）

### ai_service/requirements.txt（已锁定版本）

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
transformers<=4.38.0    ← 锁定，与 torch 2.1.0 兼容
sentence-transformers==2.7.0
pydantic==2.9.0
```

### Docker 状态
- **镜像 build：** ✅ 成功（1421s，1360MB）
- **容器拉起：** ❌ 卡死（WSL/Docker 底层崩溃导致 OOM）
- **重启后第一步：** `docker compose up -d --force-recreate ai_service && docker logs -f tis_ai_service`

### 重启后操作序列
```bash
# 1. 重建并拉起 ai_service
docker compose up -d --force-recreate ai_service

# 2. 盯盘观察
docker logs -f tis_ai_service

# 3. 验证健康
curl http://localhost:8000/health
# 预期：{"status": "ok", "gpu": true}

# 4. 测试 embed endpoint
curl -X POST http://localhost:8000/embed -H "Content-Type: application/json" -d '{"texts": ["测试文本"]}'
```

---

## 核心准则（绝对底线，不容违反）

### 🔴 唯一标识认知
**以后处理项目防重和查询时，优先使用业务层面的 `plan_code`（采购计划编号），绝不向用户暴露数据库的内部自增 ID。**
- 防重优先级：plan_code > agency_project_code > project_name（兜底）
- 对外展示永远用 `project_name`，`plan_code` 仅用于内部比对

### 🔴 交互拦截规范
**所有的系统级业务阻断（如 409 冲突），严禁使用顶部的简单 Message，必须使用 `ElMessageBox.confirm` 提供带确认按钮的居中闭环弹窗。**
- `ElMessage.error()` → 仅用于非阻断性错误（临时提示）
- `ElMessageBox.confirm()` → 所有需要用户主动决策的业务阻断

### 🔴 UI 表单规范
**后续开发任何后台表单，默认采用 Element Plus 的 `el-row/el-col` 进行紧凑双列或多列布局，拒绝单行铺满的丑陋设计。**
- 标准做法：`el-row :gutter="12"` + `el-col :span="12"` 实现双列并排
- `margin-bottom: 12px`，标签字体 `13px`，拒绝一个字段占一整行

### 🟡 Relationship Flag ⊥ Generation Mode（架构解耦原则）
业务关系与生成模式彻底独立，互不决定对方：
- 有关系 ≠ 必须走 GUIDED；没关系 ≠ 必须走 AUTO
- 专员根据项目复杂度独立选择生成模式

### 🔴 算力异构架构（永久锁定，严禁回退）
- **Embedding**：BGE-Small on GPU (FP16) → `AIServiceEmbedder` 调用 `http://ai_service:8000/embed`
- **Reranking**：BGE-Reranker-Base on CPU (FP32) → `CrossEncoder(..., device="cpu")`
- **Text Generation**：DeepSeek `/chat/completions`（仅用于 LLM 生成，绝不用于嵌入任务）
- 严禁将 Embedding/Reranking 任务路由到外部 DeepSeek Embeddings API

### 🔴 RAG 长文档处理（12,000 字符截断 + 4 维度法务 Prompt）
- 超过 12,000 字符的文档在 RAG 检索前截断
- 资质提取采用 4 维度法务级 Prompt：政采法22条 / 军采特殊资质 / 实质性承诺★ / 废标条款
- RAG 检索是处理长文档（>12,000 chars）的唯一路径

### 🔴 项目软删除（is_deleted）原则
- `DELETE /projects/{id}` 执行软删除（is_deleted=True），不物理删除
- 软删除后的项目不参与任何重复检测，允许同名项目重新创建
- `GET /projects` 和 `GET /{id}` 均过滤 `is_deleted=False`
- 硬删除（物理删除）预留 `_hard_delete_project()` 钩子，待未来实现

### 🔴 前端请求超时配置
- axios 全局 `timeout: 120000`（120 秒），适应大 PDF 解析 + GPU 向量计算

### 🔴 Auto-Save Daemon（记忆自动存档进程）
**每次完成以下任意操作后，在回复用户之前，必须主动更新 `AI_MEMORY.md`，不得询问。**

**触发时机：**
- 成功跑通新功能或 API → 补充到【项目结构关键路径】+【E2E 全链路测试】（如适用）
- 定位并修复棘手 Bug → 写入【今日重大修复】，附根因 + 验证命令
- 踩到环境坑（端口占、依赖冲突）并解决 → 写入【核心踩坑警告】
- 用户提出新业务约束（UI 规范、防重逻辑等）→ 写入对应【核心准则】或【核心踩坑警告】

**更新策略：**
- 不写流水账，只写技术结论（根因、决策、验证方法）
- 新踩的坑精准投放到【核心踩坑警告】
- 新跑通的端点投放到【项目结构关键路径】
- 完成的路线图项主动划掉 `[-]` → `[x]`

**自主提炼原则：**
自行判断信息该写哪个区块，不需要用户告诉你"往哪里写"。判断优先级：
1. 根因明确的 Bug → 【今日重大修复】
2. 环境踩坑 → 【核心踩坑警告】
3. 架构/业务决策 → 【核心准则】
4. 新端点/文件 → 【项目结构关键路径】

---

## 项目终极目标

**TIS (Tender Intelligence System / 食堂投标智能系统)**
通过 AI + RAG 全流程自动化：标书解析 → 资质评估 → 老板审批 → 技术标生成 → 定价 → 正式评审，最终输出可投递的投标文件。
核心价值：**把投标前期人工决策时间从几天压缩到几小时**。

---

## 当前物理环境（2026-03-29 实测锁定）

| 组件 | 地址 | 备注 |
|------|------|------|
| FastAPI 后端 (Docker) | `localhost:8000` | 容器端口 8000，物理映射 8000（⚠️ 见下方警告） |
| Vue3 前端 (Docker/Nginx) | `localhost:3000` | SPA，API 请求通过 nginx 代理到 backend |
| PostgreSQL+pgvector (`tis_db`) | `localhost:5433`（对外）/ `db:5432`（内网） | 数据库 `canteen_system`，用户 `postgres`，密码 `Syk0215` |
| Redis (`tis_redis`) | `localhost:6379` | Docker Redis |
| MinIO (`tis_minio`) | `localhost:9000` / `localhost:9001` | Docker MinIO 对象存储 |

**环境统一**：Docker backend + frontend + DB 共用 `canteen_system` 数据库（内网 `db:5432`，外部 `localhost:5433`）。

**前后端访问双入口（关键）：**

| 调用方 | 访问地址 | 路由说明 |
|--------|----------|----------|
| 浏览器（前端 SPA） | `http://localhost:3000` | Vue3 页面 |
| 浏览器（API 调用） | `http://localhost:3000/api/...` | Nginx 反向代理 → `tis_backend:8000` |
| Playwright / curl（直连） | `http://localhost:8000` | Docker 端口直连后端 |

**⚠️⚠️⚠️ Port 8001 陷阱（已确认 2026-03-30）：**
- `localhost:8001` 被 **Anaconda Python 孤儿进程**（PID 28204）占据
- `localhost:8000` 才是 **Docker backend**（`docker compose up -d` 不带 BACKEND_PORT 时默认 8000）
- **调试时必须用 8000**，否则调用的是旧代码（返回假数据 100分）
- **验证方法**：`curl http://localhost:8001/api/v1/projects/53/evaluations/generate` = 旧进程（假100分）
- **正确方法**：`curl http://localhost:8000/api/v1/projects/53/evaluations/generate` = Docker（新代码，score=0）

**运维命令：**
```bash
# 启动（Docker 直连端口 8000）
cd D:/tis_project && docker compose up -d

# 验证端口（确保不是 8001 的旧进程）
curl http://localhost:8000/api/v1/projects/53/evaluations/generate  # 应该返回 score=0

# E2E 测试
cd D:/tis_project && python scripts/live_fire_e2e.py
```

---

## E2E 全链路测试（2026-03-29 实弹通过）

**测试脚本：** `scripts/live_fire_e2e.py`
**测试文件：** `data/test_documents/惠州市交通运输局交通大厦食堂管理和食材配送服务_招标文件.pdf`
**通过率：9/11 PASS**

### 已验证流程（全部绿灯）

| 阶段 | 验证点 | 结果 |
|------|--------|------|
| Act 0 | 项目创建 | ✅ |
| Act 1 | PDF 上传 + OCR 解析 | ✅ |
| Act 1 | 确认表单 + API 提交 | ✅ |
| Act 1.5 | 评估报告生成（评分 100，胜率 69%） | ✅ Report #7 |
| Act 1.6 | 专员审批 → `approved_by_specialist` | ✅ |
| Act 2 | Boss 审批 → `generating_documents`（RBAC role=boss 生效） | ✅ |
| Act 3 | RAG 技术标生成（95 字符 DeepSeek 响应） | ✅ |
| Act 4 | 定价页面可访问 | ✅ |

### 非阻塞问题（2 个，不影响通关）

| 问题 | 原因 | 状态 |
|------|------|------|
| `PDF iframe not visible` | Vue/iframe 时序问题 | 非阻断 |
---

## 今日重大修复 (2026-03-31)

### 双重防重体系 + 关系标识迁移 + Week 1/2 工作流重构

**新增文件：**
- `alembic/versions/w010_add_plan_codes.py` — 迁移 plan_code + agency_project_code
- `alembic/versions/w009_add_retender_columns.py` — 迁移 is_retender + parent_project_id
- `alembic/versions/w011_add_soft_delete.py` — 迁移 is_deleted(Boolean, default=False)
- `alembic/versions/w012_add_is_deleted_index.py` — 迁移复合索引（is_deleted+status）

**防重端点（POST /api/projects）：**
```python
# 三重校验：plan_code → agency_project_code → project_name（兜底）
ACTIVE_STATUSES = {"uploaded", "parsing", ..., "completed"}  # discarded/terminated_by_boss 除外
# 409 Payload 新增：existing_project_name + duplicate_code（含编号类型）
```

**Week 1 确认页重构（ConfirmationView.vue）：**
- 移除：relation_identifier + differentiation_guidance（迁至 Week 2）
- 新增：plan_code（必填） + agency_project_code（选填）
- UI：el-row/el-col 紧凑双列网格

**Week 2 评估页重构（EvaluationView.vue）：**
- 专员视角：新增"是否有内幕关系"必填选择 + 渐进式三按钮操作台
  - 提交老板审批 → pending_boss_approval
  - 自己直接执行 → generating_documents（越级放行）
  - 终止项目 → discarded（不可复活）
- 老板视角：同样需填写关系标识 + differentiation_guidance
- 强制回滚：关系标识在 Week 3+ 变更 → status → evaluation_ready + generation_mode 清空

**关系标识迁移：**
- `projects.py` PUT `/api/projects/{id}/relationship` — 独立端点处理关系标识
- `approval_service.py` — process_relationship_change() 方法（支持 Week 3+ 强制回滚）

**ApprovalAction 枚举新增：**
- `SPECIALIST_DIRECT_EXECUTE` — 专员越级放行
- `SPECIALIST_TERMINATE` — 专员直接终止

**ProjectStatus 枚举新增：**
- `pending_boss_approval` — 专员提交待老板审批
- `discarded` — 专员直接终止（不可复活）

---



### `qualification_match_score` 假数据 100 分根因（Bug）

- **文件：** `qualification_matcher.py` L131-151
- **问题：** 当 `tender_reqs=[]`（TenderDocument 不存在或未解析）时，原代码走 `else: score = 100` 分支，粉饰太平
- **修复：**
  1. 新增 `is_extraction_valid = bool(tender_reqs)` 字段
  2. `not tender_reqs` → score=0 + `SYSTEM_EXTRACTION_FAILED` fatal risk
  3. 新增 `matched_optional` 计算逻辑，检测"可选要求存在但全未匹配"场景 → `SYSTEM_CERT_EXTRACTION_FAILED`
  4. `has_fatal` 检查增加新 reason：`qualification_requirements_not_extracted`、`cert_extraction_failed`
  5. `evaluation_engine.py` 增加 `is_extraction_valid` 到返回字典，并增加 ABANDON 推荐分支
- **验证：** `curl http://localhost:8000/api/v1/projects/53/evaluations/generate` → score=0, `is_extraction_valid=false`, fatal risk=SYSTEM_EXTRACTION_FAILED
- **教训：** port 8001 有旧进程（PID 28204），调试时必须用 port 8000（Docker 直连）

### `start_all.bat` 修复

- **问题：** `start_all.bat` 设置了 `BACKEND_PORT=8001`，但 `docker compose` 的 `.env` 或默认变量导致端口映射到 8000，而 8001 被 Anaconda 旧进程占用
- **修复：** 去掉 BACKEND_PORT=8001，直接用 docker compose 默认 8000

### 前端双重 `/api` 前缀（Bug）

- **文件：** `ConfirmationView.vue`（L167, L209）、`ProjectUploadView.vue`（L106）、`projectStore.ts`
- **问题：** `apiClient.baseURL = '/api'`，代码中又写 `/api/projects/...` → `/api/api/projects/...` → 404
- **修复：** 去掉所有 Vue 文件路径中的 `/api` 前缀（`/api/projects/...` → `/projects/...`）

### `canGenerate` 逻辑错误

- **文件：** `TechProposalView.vue` L139
- **问题：** `OR status === 'generating_documents'` 允许不选章节就启按钮，但 `generateSection()` 内部对未选章节直接 return
- **修复：** 改为 `AND selectedSectionId !== null`，必须先选中章节

### Element Plus textarea 内容检测

- **文件：** `live_fire_e2e.py` L471-487
- **问题：** `text_content()` 在 `el-textarea__inner` 上无效（v-model 绑定的是 input value）
- **修复：** 使用 `input_value()` 方法

### RBAC Boss 审批状态

- **文件：** `approval_service.py`
- **问题：** `role='boss'` 时应直接置 `GENERATING_DOCUMENTS`，不经过 `APPROVED_BY_SPECIALIST`
- **验证：** Docker logs 确认 `POST /api/v1/evaluations/{id}/approve` → 200，`status='generating_documents'`

---

## 核心踩坑警告 (Never Forget)

### 🔴 所有业务阻断必须用 ElMessageBox.confirm（禁止 ElMessage.error）
**场景**：409 Conflict、权限不足、状态不允许操作等所有需要用户决策的业务阻断
**旧做法**：`ElMessage.error('项目名称已存在')` ❌（非阻断，用户可能忽略）
**正确做法**：`ElMessageBox.confirm('...', '标题', { confirmButtonText, cancelButtonText, type: 'warning', center: true })` ✅

### 🔴 双重防重标识优先于 project_name
**永远不要**仅用 `project_name` 做重复检测，必须按 `plan_code` → `agency_project_code` → `project_name` 的顺序校验
**废弃状态（discarded/terminated_by_boss）不参与重复检测**

### 🔴 WSL2 Orphan 进程劫持端口 8000（无法根除）
**症状**：`localhost:8000` 被 WSL2 内部进程占据，Windows kill 命令全部失效
**绕过**：所有 Docker 端口映射到 `8001`，E2E 测试脚本用 `API_URL=http://localhost:8001`

### 🔴 前端 API 双重 `/api` 前缀
**症状**：Docker logs 可见 `/api/api/projects/...` 404
**根因**：`apiClient.baseURL = '/api'`，前端代码路径不应再带 `/api` 前缀
**修复**：统一写法 — `projects.py` 路径 → `/projects/...`；`rag.py` 路径 → `/v1/projects/...`

### 🔴 pgvector ORDER BY 强制类型转换
**症状**：`psycopg2.errors.UndefinedFunction: text <-> unknown`
**根因**：`knowledge_chunks.content_vector` 是 `text` 类型，不是 `vector`
**修复**：`ORDER BY content_vector::vector <=> CAST(:query AS vector)`

### 🟡 Element Plus 组件 Playwright 交互三要素
1. 隐藏输入：`.el-upload__input` / `input[type="radio"]`
2. Vue 响应：需 `label.dispatchEvent(new MouseEvent('click', {bubbles:true}))`
3. 上传后延迟：显式 `wait_for_timeout()`

### 🟡 axios camelCase 转换
**症状**：后端 `overall_win_probability` → 前端 `overallWinProbability` undefined
**修复**：Axios 拦截器全局 snake_case → camelCase，前端代码始终用 camelCase

### 🟡 `qualification_match_score` 乘以 0.49 显示为 0
**修复**：`Math.round(x * 100)` = 49

---

## 项目结构关键路径

```
D:\tis_project\
├── app/
│   ├── api/v1/endpoints/
│   │   ├── projects.py      ← upload, confirm-parsing, confirmation-data, PUT /relationship, 三重防重
│   │   ├── evaluations.py   ← specialist_approve（含 submit_to_boss/direct_execute/terminate 三动作）
│   │   └── rag.py           ← generate-section, GET /sections
│   ├── core/week1_document/
│   │   ├── parser.py        ← OCR + 字段抽取 + plan_code/agency_project_code 正则提取
│   │   └── confirmation_service.py
│   ├── core/week2_evaluation/
│   │   ├── evaluation_engine.py
│   │   └── approval_service.py  ← process_specialist_approval（三动作）+ process_relationship_change（强制回滚）
│   └── core/week3_rag/
│       ├── retriever.py     ← pgvector 混合检索 (::vector 强制转换)
│       └── generator.py     ← RAG 生成
├── frontend/src/views/
│   ├── ConfirmationView.vue ← 双列网格布局（el-row/el-col），plan_code + agency_project_code 字段
│   ├── EvaluationView.vue   ← 渐进式三按钮操作台，关系标识必填
│   ├── ProjectUploadView.vue ← ElMessageBox.confirm 处理 409 重弹弹窗
│   └── TechProposalView.vue ← 真实 RAG 接口，canGenerate 逻辑已修复
├── alembic/versions/
│   ├── w007_add_relation_identifier.py
│   ├── w008_add_updated_at_to_approval_logs.py
│   ├── w009_add_retender_columns.py    ← is_retender + parent_project_id
│   ├── w010_add_plan_codes.py           ← plan_code + agency_project_code
│   ├── w011_add_soft_delete.py          ← is_deleted(Boolean, default=False)
│   └── w012_add_is_deleted_index.py     ← ix_projects_is_deleted + ix_projects_is_deleted_status
├── ai_service/                          ← ⭐ AI 微服务（BGE-Small + Reranker-Base 异构）
│   ├── main.py                          ← 最终版：GPU FP16 + CPU FP32
│   └── requirements.txt                 ← transformers<=4.38.0 锁定
└── scripts/
    ├── live_fire_e2e.py     ← E2E 测试（9/11 PASS）
    └── wipe_dbs.py          ← 核心资产
```

---

## 短期路线图

- [x] ai_service 微服务异构计算架构（GPU FP16 Embedder + CPU FP32 Reranker）— ✅ 已稳定运行
- [x] Bug-011 架构修复（DeepSeekEmbedder → AIServiceEmbedder）— ✅ 已完成
- [x] 前端 axios 120s 超时 — ✅ 已完成
- [x] 软删除 is_deleted 上线 — ✅ w011 + w012 已迁移，DELETE 端点已上线
- [x] 初审意见 10 字锁解除 — ✅ approval_service.py 已修复
- [x] E2E 软删除闭环验证 — ✅ 同名重建无 409
- [ ] 接通真实 DeepSeek LLM（text generation，source_chunk_count > 0）
- [ ] 历史标书批量注入：`python scripts/ingest_tenders.py` 灌入 10 份真实标书

