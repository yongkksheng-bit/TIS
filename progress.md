# TIS 项目评估进度日志

## Session: 2026-05-01 修复执行

### 开始时间
2026-05-01

### 任务
1. 调查 historical_bids=0 的根因
2. 修复 outcome_book.csv（添加 historical_tender_id 列）
3. 验证 RAG 双轨功能

### 完成状态
✅ 选项A: outcome_book.csv 修复完成
✅ 选项C: RAG 双轨验证通过
⏸️ 选项B: 延后处理弃用 chunks

---

## Session: 2026-04-28 系统评估

### 开始时间
2026-04-28

### 评估状态
✅ 全部完成（Phase 1-4 + P0数据修复 + 架构修复）

### P0修复记录（2026-04-28）
- [x] win_signal 批量修复：UPDATE 13726 rows → positive=6140, negative=7585, neutral=1
- [x] retrieve_positive_samples() 返回5条 ✅
- [x] retrieve_negative_samples() 返回5条 ✅

### 架构修复记录（2026-04-28）
- [x] 根本性修复outcome_book匹配问题
  - `outcome_book.py`: 新增 `get_by_project_name()` + `_strip_doc_suffix()` + `_rows_by_project` 索引
  - `run_import.py`: 在 `step_load_bid_and_chunks` 中新增 level-3/4 fallback（project_name匹配 + 模糊匹配）
  - 修复: CSV skip逻辑, "failed"映射, header trailing space
- [x] test_outcome_book.py 新增: 7个测试用例全部通过 ✅

### 进度记录

#### 2026-04-28 12:xx
- [x] 初始化 planning-with-files 三文件
- [x] Phase 1: 环境探索（完成）
  - 项目结构：FastAPI分层 + DDD架构，8个API端点，31张DB表
  - Git历史：78dfe51~c726e9e，30条commits，master分支
  - 配置文件：docker-compose, .env.example, requirements.txt
  - 数据库：31张表全部存在，pgvector配置正常
- [x] Phase 2: 核心代码分析（完成）
  - API端点：projects, documents, evaluations, rag, pricing, formal_review
  - RAG模块：双轨RAG(retriever 421行, generator 316行) + V3 chunker(697行)
  - 定价引擎：game_theory(298行) + price_benchmark(246行)
  - 正式评审：formal_review_engine(564行)
- [x] Phase 3: 代码质量评估（完成）
  - 大文件：Top5 (908行/810行/718行/692行/564行)
  - 技术债务：P0无紧急项，P1有3项，P2有2项，P3有2项
  - 测试覆盖：60+文件，Week1-6+unit全覆盖
- [x] Phase 4: 综合评估（完成）
  - 风险识别：P1(3项) + P2(2项) + P3(2项)
  - 优化建议：P1字段填充+RAG E2E验证+历史数据注入
  - 下一步计划：P0(3项立即行动) + P1(3项本周) + P2(3项计划)

#### 重要发现
1. **w013-w018 迁移文件状态澄清**：所有6个文件已TRACKED（commit 6be65bc），非"untracked"
2. **live_fire_e2e.py 状态澄清**：579行文件存在且TRACKED，AI_MEMORY误记为"已删除"
3. **w015 metadata字段空白**：RAG系统12个新字段未填充
4. **大文件技术债**：5个400+行文件（historical_chunker 908行最高）
5. **win_signal双轨RAG失效**：13,726条chunks 100%='neutral' → 已通过SQL修复
6. **outcome_book.csv根本性缺陷**：tender/bid文件SHA256不匹配 → 已通过架构修复

#### 错误记录
| 错误 | 尝试 | 解决 |
|------|------|------|
| AI_MEMORY.md 误记 w013-w018 为 untracked | 核对 git ls-files | 确认全部已tracked（commit 6be65bc）|
| AI_MEMORY.md 误记 live_fire_e2e.py 为已删除 | 核对 git ls-files + wc -l | 文件存在（579行），确认 TRACKED |
| AI_MEMORY.md 误记 7,070 条 chunks | 直接查询 DB COUNT(*) | 实际 13,726 条 |
| AI_MEMORY.md 误记 w015 字段未填充 | 查询 DB column stats | source_type/id/win_signal/token_count 100%已填充 |
| outcome_book.csv tender/bid hash不匹配 | SQL UPDATE修复 | win_signal已正确分布 |
| outcome_book.csv架构缺陷 | 代码重构 | get_by_project_name() 新增 |

---

## Session: 2026-05-02 系统全面审查

### 开始时间
2026-05-02

### 审查发现

#### CRITICAL: projects表=0
- RAG知识库：13,726 chunks ✅
- 历史标书：14条 ✅
- 历史投标：14条 ✅
- **实际项目：0条** ⚠️

#### 系统状态
| 模块 | 状态 |
|------|------|
| chunks表 | ✅ 13,726条 |
| scoring_dimension_tags | ✅ 100%填充 |
| win_signal | ✅ positive:3153, negative:3917 |
| historical_bids | ✅ 14条 |
| RAG双轨 | ✅ 工作正常 |
| **projects表** | ⚠️ **0条** |

### 待处理

| 优先级 | 任务 | 状态 |
|--------|------|------|
| **P0** | ~~创建测试项目解锁流程~~ | ✅ 已完成 |
| **P1** | ~~端到端流程测试~~ | ✅ Week 1-2 通过 |
| **P2** | 选项B延后处理 | ⏸️ 延后 |

---

## Session: 2026-05-11 Week 1-2 E2E 测试

### 开始时间
2026-05-11

### 任务
使用 Subagent-Driven Development 执行 Week 1-2 E2E 测试

### 完成状态
✅ Task 1: 创建测试项目 - Project 117 created
✅ Task 2: 上传招标文件 - tender_documents 1 row
✅ Task 3: 触发初筛评估 - report_id=99 generated
✅ Task 4: 验收确认 - 全部criteria通过

### 执行方式
- Subagent-Driven Development（每个Task一个subagent）
- Task 1: Docker验证 → 项目创建 → DB验证
- Task 2: 文件上传 → DB验证
- Task 3: 触发评估 → DB验证
- Task 4: 三表计数验证

### 测试数据
- 项目：HZ_2025_Canteen_Test (id=117)
- 招标文件：2025_惠州交通大厦食堂管理和食材配送服务_招标文件.docx
- 评估结果：recommendation="abandon", risk_level="high"（新项目无资质数据，符合预期）

### 模型修复记录
- 文件：`app/models/historical.py`
- 问题：双向FK冲突 `AmbiguousForeignKeysError`
- 修复：移除 `HistoricalBid.postmortem` 和 `InternalPostmortem.bid` 的 `back_populates`
- 决策：**正式提交**（必要修复）

---

## Session: 2026-05-11/12 Week 3 RAG 生成测试

### 开始时间
2026-05-11 ~ 2026-05-12

### 任务
使用 Subagent-Driven Development 执行 Week 3 RAG 生成测试

### 完成状态
✅ Task 1: 生成第一章（冷链配送方案） - 2579 chars
✅ Task 2: 生成第二章（食材溯源方案） - 5836 chars
✅ Task 3: 生成第三章（服务保障方案） - 7261 chars
✅ Task 4: 保存章节到数据库 - 3 rows in project_sections
✅ Task 5: 验收确认 - GET /sections 返回 3 条

### 测试数据
- 项目：HZ_2025_Canteen_Test (id=117)
- 3 个章节已生成并保存到 project_sections 表

### 执行方式
- Subagent-Driven Development（每个Task一个subagent）
- Task 1-3: 调用 POST /generate-section 生成章节
- Task 4: 调用 PUT /sections/{name} 保存章节（发现问题：需单独保存）
- Task 5: 验证 GET /sections 和 DB 查询

### 关键发现

1. **POST /generate-section 不自动保存**：前端负责调用 PUT 保存
2. **source_chunk_count = 0**：Project 117 自身文档未建立 RAG 索引
3. **双轨 RAG 正常**：`use_dual_track_rag=true` 工作正常

---

## Session: 2026-05-12 Week 4 定价博弈测试

### 开始时间
2026-05-12

### 任务
使用 Subagent-Driven Development 执行 Week 4 定价博弈测试

### 完成状态
✅ Task 1: 设置项目预算 - budget_amount=9,000,000
✅ Task 2: 创建成本估算 - cost_estimate id=49, total_cost=9,000,000
✅ Task 3: 确认成本估算 - is_confirmed=true
✅ Task 4: 生成 A/B/C 定价方案 - 3 scenarios
✅ Task 5: 提交定价决策 - pricing_decision id=16, boss_final_price=9,200,000
✅ Task 6: 验收确认 - 数据库验证通过

### 执行方式
- Subagent-Driven Development（每个Task一个subagent）
- Task 1: SQL UPDATE 设置预算
- Task 2: POST /cost-estimates 创建估算
- Task 3: POST /cost-estimates/{id}/confirm 确认
- Task 4: POST /pricing-calculations 生成方案
- Task 5: POST /pricing-decisions 提交决策（使用 price=9,200,000 避免 loss pricing）
- Task 6: 数据库计数验证

### 测试数据
- 项目：HZ_2025_Canteen_Test (id=117)
- 预算：9,000,000
- 成本：food_cost=6,300,000, logistics_cost=1,350,000, labor_cost=900,000, management_cost=450,000
- 定价决策：boss_final_price=9,200,000, status='decided'

### 关键发现

1. **Loss Pricing Intercept**: POST /pricing-decisions 使用 price=8,800,000 被拒绝（低于成本 9,000,000）
2. **中文编码问题**: curl JSON 中文 payload 解析错误，使用文件重定向解决
3. **博弈模型正常**: A/B/C 三方案正确生成，recommended 方案被标记

---

## Session: 2026-05-12 Week 5 形式审查测试

### 开始时间
2026-05-12

### 任务
使用 Subagent-Driven Development 执行 Week 5 形式审查测试

### 完成状态
⚠️ Task 1: 查询 TechProposalTask - endpoint 返回 404，跳过
⚠️ Task 2: 确认 TechProposalTask - 同上，跳过
✅ Task 3: 发起形式审查 - 10 items, fatal_count=1
✅ Task 4: 查看评审状态 - fatal_pending=1
✅ Task 5: 确认 fatal 评审项 - confirmed
✅ Task 6: 生成最终标书 - Word doc created
✅ Task 7: 验收确认 - formal_review_items=10, final_bid_documents=1

### 执行方式
- Subagent-Driven Development（每个Task一个subagent）
- Task 1-2: 尝试查询/确认 TechProposalTask，发现 endpoint 不存在
- Task 3: POST /formal-review/initiate 生成评审清单
- Task 4: GET /formal-review/status 查看状态
- Task 5: POST /formal-review-items/{id}/confirm 确认 fatal 项
- Task 6: POST /final-documents/generate 生成 Word 文档
- Task 7: 数据库计数验证

### 测试数据
- 项目：HZ_2025_Canteen_Test (id=117)
- 形式审查：10 checklist items
- Fatal 项：1个 (check_item_id=1)
- 最终标书：/tmp/final_bid_117_20260512062831.docx

### Bug 修复记录

#### Bug 1: formal_review_items.system_status CHECK constraint
- 问题：'pending' not in allowed values
- 修复：ALTER TABLE 添加 'pending' 到 CHECK 约束

#### Bug 2: document_type 'final_bid' CHECK constraint
- 问题：'final_bid' not in allowed values (allowed: 'complete', 'draft', 'submitted')
- 修复：将 formal_review.py 中的 document_type='final_bid' 改为 'complete'

---

## Session: 2026-05-12 Week 6 Evolution 测试

### 开始时间
2026-05-12

### 任务
使用 curl 执行 Week 6 Evolution API 测试

### 完成状态
✅ Task 1: 记录 lose 结果 - bid_outcomes id=2
✅ Task 2: 查询评审分析 - outcome_status='lose'
✅ Task 3: 确认评审分析 - reviewed_by=1, review_notes 已设置
✅ Task 4: Rebid Alert - is_rebid=false
✅ Task 5: 知识进化报告 - total_chunks=13726
✅ Task 6: 记录 disqualified 结果 - disqualification_traps id=2
✅ Task 7: 验收确认 - 全部表验证通过

### Bug 修复
- CHECK constraint `disqualification_traps.trap_category` 缺少 fatal_* 值 → 已添加

### 关键发现
1. **disqualification_type 映射**: request 发送 fatal_qualification，db 记录为 fatal_formal
2. **winning_dna = 0**: Project 117 无 confirmed TechProposalTask
3. **knowledge_evolution_logs = 0**: Project 117 自身无 chunks

---

## Session: 2026-05-13 代码清理 + 双轨 RAG 验证

### 开始时间
2026-05-13

### 任务 1: Git 状态清理

**完成状态：** ✅ 完成

**操作：**
1. 检查未提交文件：117 个文件被修改/新增
2. 分类核心开发文件 vs 临时文件
3. 提交核心开发文件（docs/ 移动、AI memory 更新）
4. 删除废弃文件（scripts/deep_bid_analysis/、seed_db.py 等）

**清理结果：**
- 删除 19 个废弃文件（-20565 行代码）
- 提交 3 个 commit
- 剩余未提交：settings.local.json（本地配置）+ .minimax/（外部缓存）

**提交记录：**
```
36521e1 chore: remove obsolete files and directories
e026db8 chore: add legacy memory file
278b124 docs: move Week docs to docs/ and update AI memory files
```

### 任务 2: 双轨 RAG 验证

**完成状态：** ✅ 通过

**验证方法：**
```python
# 在 tis_backend 容器执行
retriever.retrieve_positive_samples(query='冷链配送', top_k=3)
retriever.retrieve_negative_samples(query='冷链配送', top_k=3)
```

**验证结果：**
- Positive samples: 3 ✅
- Negative samples: 3 ✅

**数据库状态确认：**
- win_signal=positive: 6,140 chunks
- win_signal=negative: 7,585 chunks

**结论：** 双轨 RAG 功能正常，pgvector 向量检索 + win_signal 过滤工作正常。

### 任务 3: Task 9 标记完成

**状态：** ✅ 已完成

**任务：** Task 5: (可选) 双轨 RAG 验证

**验证结果：** positive=3, negative=3，均 > 0

---

## Session: 2026-05-14 前端 API 路径修复 + 文件名修复

### 开始时间
2026-05-14

### 任务 1: 修复前端 `/api/` 前缀缺失（405 Not Allowed）

**问题根因：** 多个 Vue 组件中的 `apiClient` 调用缺少 `/api/` 前缀，请求被 nginx `location /` 捕获并返回 index.html（而非代理到 FastAPI 后端），导致所有 API 调用返回 HTML 或 405。

**影响范围：**
- `projectStore.ts` — 5处（trash/restore/hard-delete/list/fetchById）
- `ProjectUploadView.vue` — 7处（POST /projects, /upload, /restore, /clone 等）
- `DashboardView.vue` — 1处（DELETE /projects/:id）
- `EvaluationView.vue` — 1处（PUT /projects/:id/relationship）
- `PricingView.vue` — 1处（PUT /v1/projects/:id/pricing-decisions → /api/v1/...）
- `TechProposalView.vue` — 1处（PUT /v1/projects/:id/sections → /api/v1/...）

**修复 commit：**
```
81cb89b fix(frontend): add /api/ prefix to all projectStore API calls
54c28b3 fix(frontend): add /api/ prefix to all ProjectUploadView API calls
ccfb9cd fix(frontend): use real filename as project_name and add /api prefix to all remaining API calls
```

### 任务 2: 修复项目名称硬编码（409 DUPLICATE_TENDER）

**问题：** `ProjectUploadView.vue` 上传时 `project_name` 硬编码为 `'待解析项目'`，导致不同文件因同名而被后端重复检测拦截。

**修复：** 改为 `selectedFile.value?.name || '待解析项目'`，使用实际文件名。

**Commit：** `ccfb9cd`

### 任务 3: 验证物理删除功能正常

**验证结果：** `POST /api/projects/clear-trash` 返回 `{"cleared":[],"errors":[]}`，数据库 `is_deleted=True` 计数为 0，说明物理删除已正常工作。用户看到的"474条残留"是前端 API 路径错误导致无法拉取正确数据（返回 HTML）。

### 任务 4: planning-with-files 插件安装

**完成状态：** ✅ 已安装

**安装命令：** `npx skills add OthmanAdi/planning-with-files --skill planning-with-files -g`

**安装路径：** `~/.claude/skills/planning-with-files/`

**安全检查：** 无网络外发逻辑，仅本地 JSON 文件解析

### Git 推送记录

| Commit | 描述 |
|--------|------|
| `81cb89b` | fix(frontend): add /api/ prefix to all projectStore API calls |
| `54c28b3` | fix(frontend): add /api/ prefix to all ProjectUploadView API calls |
| `ccfb9cd` | fix(frontend): use real filename as project_name + /api prefix |

### Docker 重建

- 使用 `docker compose build --no-cache frontend` 确保镜像包含最新代码
- 验证：Docker 内 JS 文件包含 `selectedFile.value?.name` 和 `/api/projects` 路径

### 关键发现

1. **前端 API 路径规范**：nginx `location /api/` 代理到 `http://backend:8000$request_uri`，所有前端请求必须以 `/api/` 开头
2. **VITE_API_BASE_URL=""**：空字符串表示使用相对路径，前端 axios `baseURL=""` 时直接发相对 URL
3. **npm run build vs docker rebuild**：本地 `npm run build` 正常但 Docker rebuild 缓存旧文件，需用 `--no-cache`
4. **planning-with-files 插件**：已安装但 `/plan` 命令不可用（Claude Code 内置），skill 内容已加载到 `~/.claude/skills/planning-with-files/`

---

## 2026-05-17：固化阶段 — 建立每日集成检查点

### 任务来源
完善每日集成检查点（Superpowers 规范化补充）

### 完成状态

| # | 子任务 | 状态 | 产出文件 |
|---|--------|------|----------|
| 1 | 更新冒烟测试计划为双路径版本 | ✅ 完成 | `docs/superpowers/plans/2026-05-14-final-verification-plan.md` |
| 2 | 创建每日集成脚本 | ✅ 完成 | `scripts/daily_smoke_test.sh` |
| 3 | 更新日志模板 | ✅ 完成 | `daily_integration_log.md` |
| 4 | 记录已知小毛病 | ✅ 完成 | `findings.md` (仅记录，无代码修改) |
| 5 | 建立开发规范 | ✅ 完成 | 计划文件内置规范 |

### 关键修复

**approval_service.py 条件顺序修复 (commit 534c2b7)：**
- 问题：`elif action == 'approve'` 先于 `elif role == 'boss' and action == 'approve'` 匹配，导致 boss 审批永远无法触发
- 修复：调换 elif 顺序，使 boss 特定条件优先匹配
- 验证：Path B (submit_to_boss → boss_approve) 测试通过

### 冒烟测试双路径验证

| 路径 | 测试项目 | 结果 |
|------|----------|------|
| Path A (direct_execute) | Project 3 | ✅ 完整通过 |
| Path B (submit_to_boss → boss_approve) | Project 5 | ✅ 完整通过 |

### 已知小毛病（仅记录，不修复）

| 问题 | 位置 | 处理 |
|------|------|------|
| API路径不一致 | advance-to-pricing 使用 `/api/projects/` 而非 `/api/v1/projects/` | 记录到 findings.md |
| 状态命名不一致 | confirm-parsing 返回 `evaluating` 而非预期 `evaluation_ready` | 记录到 findings.md |
| authStore 硬编码 | user id=1, role='specialist' | 记录到 findings.md |

### 开发规范（已建立）

1. **3-Strike Error Protocol**：同一错误出现3次时停止 → 记录 → 汇报
2. **冒烟测试门禁**：提交前必须 pytest + Path A + Path B（修改approval时）全部通过
3. **小步快跑**：每次commit仅包含一个逻辑变更

### 当前阶段

**固化阶段完成 → 准备进入下一阶段**

### 相关文档

- `docs/superpowers/plans/2026-05-14-final-verification-plan.md` - 双路径冒烟测试计划
- `docs/superpowers/plans/2026-05-17-daily-checkpoint-supplement.md` - 本次补充计划
- `scripts/daily_smoke_test.sh` - 自动化冒烟测试脚本
- `daily_integration_log.md` - 每日集成日志模板
- `findings.md` - 已知问题记录
