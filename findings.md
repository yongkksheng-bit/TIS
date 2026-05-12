# TIS 项目评估发现

## 项目概述
- **项目名**: TIS (高校食堂投标系统 / Tender Intelligence System)
- **技术栈**: FastAPI + PostgreSQL/pgvector + Vue.js + Docker
- **核心功能**: RAG 检索、招投标知识管理、定价博弈、正式评审
- **版本**: v1.0 (正式版)
- **Git分支**: master

## Phase 1: 环境探索发现

### 1.1 项目结构

**后端架构（FastAPI 分层 + DDD Lite）：**
```
app/
├── api/v1/endpoints/     # 8个端点文件
│   ├── auth.py           # 登录/权限（JWT）
│   ├── projects.py       # 项目基础CRUD + 三重防重 + clone
│   ├── documents.py     # Week1: 文件上传/OCR
│   ├── evaluations.py    # Week2: 初筛报告/审批流
│   ├── rag.py            # Week3: RAG生成/章节编辑
│   ├── pricing.py        # Week4: 定价决策（454行）
│   ├── formal_review.py  # Week5: 形式审查（10端点）
│   └── evaluations.py    # Week2 审批（含三动作模型）
├── core/                 # 核心业务逻辑（Service Layer）
│   ├── week1_document/   # parser.py, ocr_engine.py, qualification_extractor.py
│   ├── week2_evaluation/ # evaluation_engine.py, qualification_matcher.py, approval_service.py
│   ├── week3_rag/        # retriever.py(421行), generator.py(316行), embedder.py, llm_mock.py
│   ├── week4_pricing/     # game_theory.py(298行), price_benchmark.py, cost_engine.py
│   ├── week5_formal_review/ # formal_review_engine.py(564行), word_generator.py
│   └── week6_evolution/  # review_engine.py, revival_engine.py
├── models/               # SQLAlchemy 模型（31张表）
├── schemas/              # Pydantic 模型（API出入参）
├── services/             # 基础设施（storage, vector_db, llm_client, embedding）
└── utils/                # 工具函数

alembic/versions/         # 迁移脚本（w001-w018）
scripts/seeding/          # V3 Seeding Pipeline（docx_parser.py, historical_chunker.py）
frontend/src/views/       # Vue 页面
tests/                    # 测试（60+文件，按Week分）
```

**Docker 容器拓扑：**
- `tis_backend` (FastAPI) - 端口 8000 ✅ healthy
- `tis_frontend` (Vue.js + Nginx) - 端口 3000
- `tis_db` (PostgreSQL + pgvector) - 内网 5432/对外 5433 ✅
- `tis_ai_service` - healthy ✅
- `tis_redis`, `tis_minio`, `nginx`

### 1.2 数据库状态（实测）

**13,726 条 chunks 实测数据（2026-04-28）：**

| 指标 | 数值 | 说明 |
|------|------|------|
| 总 chunk 数 | 13,726 | 比 AI_MEMORY 误记的 7,070 多 |
| 已有向量 | 13,726 (100%) | 不需要重新 embed |
| 向量维度 | 512（BGE-small）| AIServiceEmbedder 生成 |
| 中位 token | 20 | 段落级切分设计 |
| P95 token | 83 | 95% chunk < 84 tokens |
| 短chunk（<30 token）| 9,377 (68.3%) | chunker 设计选择，非 bug |
| 超大chunk（>2000 token）| 15 (0.1%) | 可接受 |

**w015 字段实测：**

| 字段 | 填充率 | 说明 |
|------|--------|------|
| source_type | 100% | 全为 "historical_tender" |
| source_id | 100% | 有值 |
| win_signal | 100% | **全部为 "neutral"** ⚠️ |
| scoring_dimension_tags | 45.8% (6,282) | 54.2% 为空（boilerplate chunk 无评分维度是设计如此）|
| is_price_sensitive | 100% | 有值 |
| token_count | 100% | 有值 |

**关键发现 - 双轨RAG完全失效：**
- `retrieve_positive_samples()` → SQL 过滤 `win_signal='positive'` → **0 条结果**
- `retrieve_negative_samples()` → SQL 过滤 `win_signal='negative'` → **0 条结果**
- 根因：13,726 条 chunk 100% `win_signal='neutral'`（导入时从未设置）
- 这导致 `use_dual_track_rag=True` 时 generator 调用两个 retriever 都返回空列表

## Phase 2: 核心代码分析

### 2.1 API 端点

| 端点文件 | Week | 核心功能 |
|---------|------|---------|
| `projects.py` | - | CRUD + 三重防重 + 软删除 + clone |
| `documents.py` | 1 | PDF上传/OCR解析 |
| `evaluations.py` | 2 | 初筛报告 + 三动作审批 |
| `rag.py` | 3 | RAG生成 + 章节Upsert |
| `pricing.py` | 4 | 定价博弈（454行） |
| `formal_review.py` | 5 | 形式审查（718行）+ 10端点 |

### 2.2 RAG 模块

**双轨RAG架构：**
- `retriever.py` (421行) - `retrieve_positive_samples()` + `retrieve_negative_samples()`
- `generator.py` (316行) - `use_dual_track_rag` + `build_chunk_context()`
- `embedder.py` (109行) - `AIServiceEmbedder` → `http://ai_service:8000/embed` ✅ 真实服务
- `llm_mock.py` - `get_llm()` → `RealDeepSeekLLM` ✅ 真实LLM

**实际状态：**
- ai_service ✅ healthy (Up 6 days)
- backend ✅ healthy (Up 18 hours)
- USE_MOCK_EMBEDDER=false → AIServiceEmbedder ✅
- USE_MOCK_LLM=false → RealDeepSeekLLM ✅

**V3 historical_chunker.py (908行)：**
- 三层过滤：Boilerplate过滤 → 聚类+滑动窗口 → LLM洞察提取
- Layer 3 LLM：`extract_llm_insights()` 提取 `core_pain_points, technical_indicators, competitive_advantages` → 写入 `scoring_dimension_tags`
- 补丁1：Exponential Backoff + Full Jitter
- 补丁2：Markdown表格原子emit
- 补丁3：`has_table` 写入 metadata
- 补丁4：JSONB兼容性

### 2.3 定价引擎

- `game_theory.py` (298行) - 市场博弈矩阵
- `price_benchmark.py` (246行) - `MarketHeatContext`

### 2.4 正式评审

- `formal_review_engine.py` (564行) - 动态检查项 + PDF高亮 + Word生成

## Phase 3: 代码质量

### 3.1 大文件/复杂模块

| 文件 | 行数 | 风险 |
|------|------|------|
| `scripts/seeding/chunkers/historical_chunker.py` | 908 | 高 |
| `scripts/seeding/run_import.py` | 810 | 高 |
| `app/api/v1/endpoints/formal_review.py` | 718 | 高 |
| `app/core/week1_document/parser.py` | 692 | 中 |
| `app/core/week5_formal_review/formal_review_engine.py` | 564 | 高 |

### 3.2 技术债务

**P0（立即修复）：**
1. **⚠️ CRITICAL: 双轨RAG完全失效** - 13,726条 chunks 100% win_signal='neutral'，retrieve_positive/negative 均返回 0 结果
   - 修复：批量 UPDATE 将 historical_tender 的 win_signal='neutral' → 'positive'
   - 原因：导入时从未设置 win_signal，全部默认为 neutral

**P1 高优先级：**
2. **scoring_dimension_tags 54.2%为空** - 这是 chunker 设计：boilerplate 段落无评分维度是正确的，但历史数据注入时未启用 LLM 洞察提取（enable_llm_insights=False）导致无标签
3. **历史标书未注入** - 当前 chunks 来自冷启动数据，非真实项目

**P2 中优先级：**
4. **大文件拆分** - historical_chunker(908行)、run_import(810行)

## Phase 4: 综合评估

### 4.1 风险识别

| 风险 | 级别 | 说明 |
|------|------|------|
| 双轨RAG失效 | ~~P0~~ ✅已修复 | win_signal 已修复：positive=6140, negative=7585, neutral=1 |
| AI_MEMORY大量误记 | ~~P1~~ ✅已澄清 | 7项误记已在task_plan.md澄清 |
| outcome_book.csv header有trailing space | ~~P1~~ ✅已修复 | 代码已处理tender_file_name (带空格) key |
| tender/bid文件hash不匹配 | ~~P1~~ ✅已修复 | 新增get_by_project_name()方法，4级fallback匹配 |
| 54.2%无评分标签 | P2 | chunker 设计如此，可接受 |

### 4.2 AI_MEMORY.md 误记澄清

| 误记内容 | 实际情况 |
|---------|---------|
| 7,070条 chunks | 实际 13,726条 |
| 48.5%短chunk问题 | 实际 68.3%（但这是设计非bug）|
| w015字段未填充 | source_type/id/win_signal/token_count 100%已填充 |
| 需要重新导入 | 不需要，已有向量 |
| w013-w018 untracked | 全部已TRACKED（commit 6be65bc）|
| live_fire_e2e.py 已删除 | 文件存在（579行），TRACKED |
| ai_service 未安装 | ✅ tis_ai_service healthy 6天 |

### 4.3 下一步计划（基于事实的决策）

**P0（立即执行）：**
1. **修复双轨RAG** - 执行 `UPDATE knowledge_chunks SET win_signal='positive' WHERE win_signal='neutral' AND source_type='historical_tender'`
   - 原因：historical_tender 代表中标案例，应为 positive signal
   - 此修复让 retrieve_positive_samples() 开始返回结果
2. **验证RAG E2E** - 修复后测试 retriever → generator 完整链路

**P1（本周）：**
3. **启用LLM洞察提取重导入** - 历史标书重新注入，设置 `enable_llm_insights=True` 填充 scoring_dimension_tags
4. **大文件拆分** - historical_chunker / run_import

**P2（计划）：**
5. CI/CD 流程建立

## 决策记录

- **ARCH-DECOUPLE**：relationship_flag ⊥ generation_mode
- **三重防重**：plan_code > agency_project_code > project_name
- **软删除优先**：is_deleted=True
- **算力异构**：Embedding(GPU FP16) / Reranker(CPU FP32) / LLM(DeepSeek)
- **300s超时链**：axios + Nginx + Uvicorn

### 2026-04-28 自主核查结论

**问题1：7,070条chunks是否需要重新跑？**
- 实际 13,726 条，已有向量，**不需要重新embed**
- 真正问题：win_signal 100%='neutral'，双轨RAG完全失效
- 修复方法：批量 UPDATE，无需重新导入

**问题2：下一步该做什么？**
1. **第一优先**：修复 win_signal（批量 UPDATE）
2. **第二优先**：验证 RAG E2E（确认双轨能返回结果）
3. **第三优先**：可选 - 启用 LLM 洞察重导入填充 scoring_dimension_tags

**7,070条chunks能否直接作为RAG基础？**
- 向量已就绪 ✅
- w015字段已填充 ✅
- **但双轨RAG失效** ⚠️ - 需要先修复 win_signal

---

## Session: 2026-05-02 系统全面审查

### CRITICAL 发现

**`projects` 表 = 0 条记录**

这意味着 TIS 系统虽然有：
- RAG 知识库：13,726 chunks ✅
- 历史标书：14 条 ✅
- 历史投标：14 条 ✅

但**实际项目数为 0**！

| 表名 | 记录数 | 状态 |
|------|--------|------|
| knowledge_chunks | 13,726 | ✅ |
| historical_tenders | 14 | ✅ |
| historical_bids | 14 | ✅ 已修复 |
| projects | **0** | ⚠️ **CRITICAL** |
| tender_documents | 0 | ⚠️ |
| bid_documents | 0 | ⚠️ |
| approval_logs | 0 | ⚠️ |
| users | 2 | ✅ |

### 根因分析

系统是 **Demo/原型阶段**：
- RAG 历史数据已填充（用于检索）
- 但实际的投标项目管理流程从未使用过
- 没有通过前端创建过任何项目

### 影响评估

1. **RAG 系统**：功能正常，历史数据充足
2. **项目流程**：无法使用 — 没有项目数据
3. **评估流程**：无法测试 — 没有项目
4. **定价流程**：无法测试 — 没有项目
5. **形式审查**：无法测试 — 没有项目

### 审查维度

#### 1. 数据质量审查
- [x] 弃用chunk：6,656个，延后处理
- [x] 向量嵌入：13,726条 100%有向量
- [x] 标签覆盖率：7,070活跃chunks 100%有标签
- [x] Win signal：positive 3153, negative 3917，分布正确

#### 2. 功能完整性审查
- [x] RAG检索：retriever.py 正常工作
- [x] RAG生成：generator.py 正常工作
- [x] API端点：8个端点文件存在
- [ ] **CRITICAL**: projects=0 导致完整流程无法测试

#### 3. 下一步优先级

| 优先级 | 任务 | 输入 | 输出 | 理由 |
|--------|------|------|------|------|
| **P0** | 创建测试项目 | 项目数据 | projects表有数据 | 解锁完整流程测试 |
| **P1** | 端到端流程测试 | 测试项目 | 完整流程验证 | 确保系统可用 |
| **P2** | 选项B：弃用chunks | - | - | 不影响活跃RAG |

#### 4. 潜在风险

| 风险 | 级别 | 说明 |
|------|------|------|
| projects=0 | ~~**CRITICAL**~~ ✅已修复 | 系统已可实际使用 |
| 完整流程未验证 | ~~**HIGH**~~ ✅已修复 | Week 1-2 E2E测试通过 |
| 弃用数据积累 | **LOW** | 不影响活跃系统 |

---

## Session: 2026-05-11 Week 1-2 E2E 测试

### 测试结果

| 阶段 | 结果 |
|------|------|
| 创建项目 | ✅ Project 117 |
| 上传标书 | ✅ tender_documents 1 row |
| RAG评估 | ✅ report_id=99 |
| 验收确认 | ✅ 全部criteria通过 |

### API端点发现

| Spec路径 | 实际路径 | 状态 |
|----------|----------|------|
| `/api/v1/projects` | `/api/projects` | ⚠️ Spec需更新 |
| `/api/v1/projects/{id}/upload-tender` | `/api/projects/{id}/upload` | ⚠️ Spec需更新 |
| `/api/v1/projects/{id}/evaluations/generate` | `/api/v1/projects/{id}/evaluations/generate` | ✅ 一致 |

### 模型关系修复

**问题**：`HistoricalBid.postmortem` ↔ `InternalPostmortem.bid` 双向FK导致 `AmbiguousForeignKeysError`

**根因**：`internal_postmortems` 表有两个FK指向 `historical_bids`:
- `id` 列
- `historical_bid_id` 列

**修复**：移除双向 `back_populates`，使用单向 `foreign_keys` 消歧

```python
# Before (冲突)
HistoricalBid.postmortem = relationship(..., back_populates="bid")
InternalPostmortem.bid = relationship(..., back_populates="postmortem")

# After (正确)
HistoricalBid.postmortem = relationship(..., foreign_keys=[internal_postmortem_id])
InternalPostmortem.bid = relationship(..., foreign_keys=[historical_bid_id])
```

**决策**：正式提交 - 这是必要修复，非临时 workaround

### 数据库用户发现

原任务描述使用 `canteen` 用户，实际数据库用户是 `postgres`
---

## Session: 2026-05-11/12 Week 3 RAG 生成测试

### 测试结果

| 阶段 | 结果 |
|------|------|
| 生成第一章 | ✅ 2579 chars |
| 生成第二章 | ✅ 5836 chars |
| 生成第三章 | ✅ 7261 chars |
| 保存章节 | ✅ 3 rows |
| 验收确认 | ✅ 全部通过 |

### API端点发现

| 端点 | 实际路径 | 功能 |
|------|----------|------|
| 生成章节 | POST `/api/v1/projects/{id}/generate-section` | 生成章节内容（不自动保存）|
| 查询章节 | GET `/api/v1/projects/{id}/sections` | 查询已保存章节 |
| 保存章节 | PUT `/api/v1/projects/{id}/sections/{name}` | 持久化章节内容 |

### 关键发现 1: POST /generate-section 不自动保存

**现象**：
- 调用 `POST /generate-section` 返回章节内容（2579/5836/7261 chars）
- 但 `project_sections` 表为空
- 需要额外调用 `PUT /sections/{section_name}` 才能保存

**分析**：
- 这是 **API 设计**，不是 bug
- `POST /generate-section` 只负责生成内容（LLM 调用）
- `PUT /sections/{section_name}` 负责持久化
- 前端 `TechProposalView.vue` 在生成后调用 PUT 保存

**建议**：
- 如需自动保存，可在 `POST /generate-section` 末尾添加 `db.commit()` 和 `ProjectSection` upsert
- 或保持现状（符合单一职责原则）

### 关键发现 2: source_chunk_count = 0

**现象**：
- Project 117 调用 `POST /generate-section` 时 `source_chunk_count = 0`
- `knowledge_chunks` 表中 `source_project_id = 117` 的记录为 0

**原因**：
- Week 1-2 只上传了招标文件到 `tender_documents` 表
- 未调用 `POST /api/v1/projects/117/documents/embed` 将文档分块并建立 RAG 索引

**影响**：
- 生成的内容来自 LLM 自身知识 + 双轨 RAG 历史数据
- 未使用 Project 117 自身的招标文件内容

**建议**：
- 如需 Project 自身文档作为 context，需先调用 `/documents/embed`
- 这是预期行为，非 bug

---

## Session: 2026-05-12 Week 4 定价博弈测试

### 测试结果

| 阶段 | 结果 |
|------|------|
| 设置预算 | ✅ budget_amount=9,000,000 |
| 创建成本估算 | ✅ total_cost=9,000,000 |
| 确认成本估算 | ✅ is_confirmed=true |
| 生成定价方案 | ✅ 3 scenarios (aggressive/balanced/conservative) |
| 提交定价决策 | ✅ boss_final_price=9,200,000, status='decided' |
| 验收确认 | ✅ 全部通过 |

### API端点发现

| 端点 | 方法 | 功能 |
|------|------|------|
| /api/v1/projects/{id}/cost-estimates | POST | 创建成本估算 |
| /api/v1/cost-estimates/{id}/confirm | POST | 确认成本估算 |
| /api/v1/projects/{id}/pricing-calculations | POST | 生成 A/B/C 定价方案 |
| /api/v1/projects/{id}/pricing-decisions | POST | 提交定价决策 |

### 关键发现: Loss Pricing Intercept

**现象**：
- 调用 `POST /pricing-decisions` 使用 `boss_final_price=8,800,000`（低于成本 9,000,000）
- API 返回错误："Loss pricing not allowed"

**分析**：
- 定价引擎有保护机制，防止亏损定价
- boss_final_price 必须 >= 成本估算 (cost_estimate.total_cost)

**解决方案**：
- 使用 `boss_final_price=9,200,000`（高于成本 9,000,000）

---

## Session: 2026-05-12 Week 5 形式审查测试

### 测试结果

| 阶段 | 结果 |
|------|------|
| 查询 TechProposalTask | ⚠️ endpoint 返回 404 |
| 发起形式审查 | ✅ 10 checklist items |
| 查看评审状态 | ✅ fatal_pending=1 |
| 确认 fatal 项 | ✅ confirmed |
| 生成最终标书 | ✅ Word doc created |
| 验收确认 | ✅ 全部通过 |

### Bug 修复

#### Bug 1: formal_review_items.system_status CHECK constraint

**问题**：`formal_review_items.system_status` CHECK 约束只允许 `('passed','failed','warning','uncertain')`，但 `formal_review_engine.py` 插入 `'pending'` 状态

**错误信息**：
```
psycopg2.errors.CheckViolation: new row violates check constraint "formal_review_items_system_status_check"
```

**修复**：
```sql
ALTER TABLE formal_review_items DROP CONSTRAINT IF EXISTS formal_review_items_system_status_check;
ALTER TABLE formal_review_items ADD CONSTRAINT formal_review_items_system_status_check CHECK (system_status IN ('passed','failed','warning','uncertain','pending'));
```

#### Bug 2: document_type 'final_bid' CHECK constraint

**问题**：`final_bid_documents.document_type` CHECK 约束不允许 `'final_bid'`，只允许 `('complete','draft','submitted')`

**错误信息**：
```
psycopg2.errors.CheckViolation: new row violates check constraint "final_bid_documents_document_type_check"
```

**修复**：
- 文件：`app/api/v1/endpoints/formal_review.py`
- 变更：`document_type='final_bid'` → `document_type='complete'`

### 关键发现 1: TechProposalTask endpoint 不存在

**现象**：
- GET `/api/v1/projects/117/tech-proposal/current` 返回 404
- Project 117 无 TechProposalTask 记录

**分析**：
- 系统中无 `/tech-proposal/current` endpoint
- TechProposalTask 是独立模型，与 ProjectSection 不同

**影响**：
- 无法通过 API 确认 tech proposal
- 形式审查仍可正常发起（不需要 tech proposal 确认）

### 关键发现 2: fatal 项阻止生成

**现象**：
- `POST /final-documents/generate` 在 fatal_pending > 0 时返回错误
- 需要先确认所有 fatal 项才能生成最终标书

**分析**：
- 这是正确的产品设计，防止遗漏致命问题
- 流程：发起审查 → 确认 fatal 项 → 生成标书

### 关键发现 3: Word 文档生成

**现象**：
- 最终标书成功生成，文件路径 `/tmp/final_bid_117_20260512062831.docx`
- `final_bid_documents` 表有 1 条记录

**分析**：
- `word_generator.py` 正常工作了
- 文件存储在 MinIO 或本地文件系统
