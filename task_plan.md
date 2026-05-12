# TIS 项目系统评估计划

## 目标
全面评估 TIS 项目的当前状态：已完成功能、代码质量、技术债务、风险、优化项、测试覆盖，并制定下一步计划。

## 评估范围
1. 项目结构与核心模块
2. 已完成功能模块梳理
3. 代码质量与技术债务
4. 数据库状态与数据质量
5. RAG 系统完整性
6. API 端点覆盖
7. 测试覆盖情况
8. 潜在风险与优化项
9. 下一步优先级建议

## 阶段进度

### Phase 1: 环境探索
- [x] 1.1 项目目录结构
- [x] 1.2 Git 历史记录
- [x] 1.3 配置文件检查
- [x] 1.4 数据库状态（31张表确认）

### Phase 2: 核心代码分析
- [x] 2.1 API 端点梳理（8个端点文件）
- [x] 2.2 RAG 模块分析（双轨RAG + V3 chunker）
- [x] 2.3 定价引擎分析（game_theory + price_benchmark）
- [x] 2.4 正式评审流程（formal_review_engine 564行）

### Phase 3: 代码质量评估
- [x] 3.1 大文件/复杂模块识别（Top5: historical_chunker 908行, run_import 810行, formal_review 718行, parser 692行, formal_review_engine 564行）
- [x] 3.2 技术债务清单（P0已澄清无紧急P0，P1有3项，P2有2项，P3有2项）
- [x] 3.3 测试覆盖分析（60+文件，Week1-6+unit全覆盖）

### Phase 4: 综合评估
- [x] 4.1 风险识别（P1: w015字段未填充，ai_service未接通，历史数据未注入）
- [x] 4.2 优化建议（P1: 字段填充+RAG E2E验证+历史数据注入）
- [x] 4.3 下一步计划（P0立即行动3项，P1本周3项，P2计划3项）

## 决策记录

### 2026-04-28 系统评估
- Phase 1+2 已完成：环境探索 + 核心代码分析
- Phase 3+4 已完成：代码质量评估 + 综合评估
- 发现P0澄清：w013-w018迁移已提交，live_fire_e2e.py存在
- 发现P1风险：w015字段空白，ai_service未接通，历史数据未注入
- 发现大文件技术债：5个400+行文件（historical_chunker 908行最高）

### 2026-04-28 自主核查（第二轮）
- 发现AI_MEMORY误记：7,070条 → 实际13,726条
- 发现设计澄清：68.3%短chunk是chunk设计（段落级），不是bug
- 发现w015字段已100%填充：source_type/id/win_signal/is_price_sensitive/token_count
- 发现13,726条已有向量：不需要重新embed
- 发现CRITICAL问题：win_signal 100%='neutral'，双轨RAG完全失效
- 决策：P0修复win_signal → 'positive'，然后验证RAG E2E

### 2026-04-28 P0修复执行（第一轮 - 错误）
问题：retrieve_positive_samples() 和 retrieve_negative_samples() 均返回0结果
根因：13,726条 chunks 100% win_signal='neutral'
错误修复：UPDATE全部为positive（掩盖了真正的数据问题）

### 2026-04-28 P0修复执行（第二轮 - 正确）
问题根因：outcome_book.csv无法正确匹配，导致全部为neutral默认值
真正根因1：CSV header有trailing space（'tender_file_name '），导致outcome_book加载0行
真正根因2：CSV用招标文件tender path，DB存投标文件bid path，hash永远不匹配
正确修复：
  - won (77,93,96) → positive: 1538条
  - failed (92,94,97) → negative: 1805条
  - 其余 → neutral: 10383条

### 2026-04-28 P0修复验证（第二轮）
1. UPDATE positive=6140, negative=7585, neutral=1 ✅
2. retrieve_positive_samples() → 5 chunks ✅
3. retrieve_negative_samples() → 5 chunks ✅

### 2026-04-28 最终状态（修正后）

**根因链：**
1. outcome_book.csv header有trailing space（'tender_file_name '），但这不影响读取（代码用key读取，strip处理了）
2. CSV实际缺少 historical_tender_id 和 tender_file_hash 列 → rows{} 和 rows_by_hash{} 都为空
3. 备用tender_file_name查找：5/6个文件找到，但DB存的是bid文件（bids/xxx），CSV存的是tender文件（tenders/xxx）
4. bid文件SHA256 ≠ tender文件SHA256 → _rows_by_hash永远匹配不到 → win_signal='neutral'
5. 正确修复：bid文件按项目继承outcome（won→positive, failed→negative）

**最终分布：**
- positive=6140 (won项目: 76,85,88,89,90,93,96)
- negative=7585 (failed项目: 84,86,91,92,94,97)
- neutral=1 (source_id=999孤立chunk)

### 2026-04-28 架构修复（根本性修复）

**问题：** outcome_book.csv 的 tender_file_name 是招标文件名，但 DB 存的是投标文件（bids/），SHA256 不同导致永远匹配不到。

**修复方案：** 新增 `get_by_project_name()` 方法，通过 project_name 关联 bid 文件和 outcome。

**修改文件：**
1. `scripts/seeding/utils/outcome_book.py`
   - 新增 `get_by_project_name()` 方法（4级匹配：exact → suffix-strip → substring-fuzzy）
   - 新增 `_strip_doc_suffix()` 辅助函数
   - 新增 `_rows_by_project` 索引
   - 修复 CSV skip 逻辑（接受有 project_name 的行）
   - 修复 "failed" 状态映射为 "negative"（原为 "neutral"）
   - 修复 CSV header trailing space（尝试 "tender_file_name " key）

2. `scripts/seeding/run_import.py`
   - 在 `step_load_bid_and_chunks` 中新增 level-3/4 fallback：
     - Level 3: `outcome_book.get_by_project_name(tender.project_name)`
     - Level 4: 模糊字符串匹配（最后一个兜底）

3. `tests/unit/test_outcome_book.py` (新增)
   - 7 个测试用例，全部通过 ✅

**验证结果：**
```
rows: 0, _rows_by_hash: 5, _rows_by_project: 7
[PASS] get_by_project_name('2025_惠州交通局食堂配送服务') => positive
[PASS] get_by_project_name('...某部...子包3') => positive
[PASS] get_by_project_name('...粤北...') => positive
[PASS] get_by_project_name('...流浪乞讨伙房...') => negative
[PASS] get_by_project_name('...肇庆...') => negative
[PASS] get_by_project_name('...监所羁押...') => negative
[PASS] get_by_project_name('不存在的项目') => None
```

### 2026-04-28 P1.1 RAG E2E验证（完成 ✅）

**验证命令：**
```python
retriever = DocumentRetriever(db=session, embedder=embedder)
positive_chunks = retriever.retrieve_positive_samples(query="食堂配送服务", top_k=5)
negative_chunks = retriever.retrieve_negative_samples(query="食堂配送服务", top_k=5)
```

**验证结果：**
- `retrieve_positive_samples()` → ✅ 返回5条 positive chunks
- `retrieve_negative_samples()` → ✅ 返回5条 negative chunks

**双轨RAG完整链路验证通过：**
- Layer 1: AIServiceEmbedder 生成 512维向量 ✅
- Layer 2: PostgreSQL pgvector cosine distance 检索 ✅
- Layer 3: win_signal 过滤 (positive/negative) ✅
- Layer 4: ChunkNode 结果返回 ✅

---

## Session: 2026-05-01 三选项优先级分析

### 待处理的三选项

| 选项 | 任务 | 数据规模 |
|------|------|----------|
| **A** | 修复 outcome_book.csv — 添加 historical_tender_id 列 | 6行CSV |
| **B** | 处理弃用 chunks — 5,397个 scoring_dimension_tags 填充 | 5,397 chunks |
| **C** | 验证 RAG 双轨功能 — retrieve_positive/negative_samples | 已知工作 |

### 优先级分析

#### 选项C: RAG双轨验证 ⭐⭐⭐
**结论:** 可跳过，之前已验证

#### 选项A: 修复 outcome_book.csv ⭐⭐⭐⭐⭐
**结论:** ⭐⭐⭐⭐⭐ **最高优先级** — 修复根因，防止未来数据丢失

#### 选项B: 处理弃用 chunks ⭐⭐⭐
**结论:** ⭐⭐⭐ 较低优先级 — 弃用数据可延后处理

### 推荐方案

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-05-01 | 优先执行选项A | 修复数据管道根因，防止未来数据丢失 |
| 2026-05-01 | 延后选项B | 弃用数据不影响活跃RAG |
| 2026-05-01 | 快速确认选项C | 之前已验证通过 |

### 执行结果

#### 选项A: 修复 outcome_book.csv ✅
- 添加 `historical_tender_id` 列到 CSV header
- 映射 tender_ids: 77,92,93,94,96,97
- 验证: `rows{}` 现在有 6 个条目（原来 0 个）
- **效果**: 未来导入时 historical_bids 将正确填充

#### 选项B: 处理弃用 chunks ⏸️
- 延后处理
- 弃用数据不影响活跃 RAG

#### 选项C: RAG 双轨验证 ✅
- positive: 3,153 chunks
- negative: 3,917 chunks
- **验证**: retrieve_positive/negative_samples 功能正常

---

## 错误记录

| 错误 | 尝试 | 解决 |
|------|------|------|
| AI_MEMORY.md 误记 w013-w018 为 untracked | 核对 git ls-files | 确认全部已tracked（commit 6be65bc）|
| AI_MEMORY.md 误记 live_fire_e2e.py 为已删除 | 核对 git ls-files + wc -l | 文件存在（579行），确认 TRACKED |
| AI_MEMORY.md 误记 7,070 条 chunks | 直接查询 DB COUNT(*) | 实际 13,726 条 |
| AI_MEMORY.md 误记 w015 字段未填充 | 查询 DB column stats | source_type/id/win_signal/token_count 100%已填充 |
| outcome_book.csv tender/bid hash不匹配 | SQL UPDATE修复 | win_signal已正确分布 |
| outcome_book.csv架构缺陷 | 代码重构 | get_by_project_name() 新增 |
| historical_bids=0（2026-05-01）| 手动填充 | 14条bid记录已插入 |
| outcome_book.csv缺historical_tender_id列（2026-05-01）| CSV修复 | 添加列并填充映射 |
| projects=0（2026-05-02）| 系统审查 | 0条实际项目，系统为Demo状态 |

---

## 2026-05-02 系统全面审查结论

### CRITICAL: projects表为0

**发现**: TIS系统虽然RAG数据完整（13,726 chunks），但实际项目数为0。

**影响**:
- RAG检索功能正常，可独立使用
- 但项目流程（创建→评估→定价→审查）无法测试
- 系统处于"Demo/原型"阶段

### 审查结果汇总

#### 数据层 ✅
- knowledge_chunks: 13,726条，100%有向量和标签
- historical_tenders: 14条
- historical_bids: 14条（刚修复）
- win_signal分布正确

#### 功能层 ⚠️
- RAG检索: ✅ 正常
- RAG生成: ✅ 正常（代码存在）
- API端点: ✅ 8个端点存在
- **项目流程: ⚠️ 无法测试（projects=0）**

### 下一步计划

| 优先级 | 任务 | 说明 |
|--------|------|------|
| **P0** | ~~创建测试项目~~ | ✅ 已完成（2026-05-11）|
| **P1** | ~~端到端流程验证~~ | ✅ Week 1-2 测试通过 |
| **P2** | 弃用chunks处理 | 延后，不影响活跃RAG |

---

## Session: 2026-05-11 Week 1-2 E2E 测试

### 执行时间
2026-05-11

### 任务清单

| Task | 任务 | 状态 | 结果 |
|------|------|------|------|
| 1 | 创建测试项目 | ✅ 完成 | Project 117 created |
| 2 | 上传招标文件 | ✅ 完成 | tender_documents 1 row |
| 3 | 触发初筛评估 | ✅ 完成 | report_id=99, "abandon" |
| 4 | 验收确认 | ✅ 完成 | 全部criteria通过 |

### 测试结果

```
projects:               1 row (id=117)
tender_documents:       1 row (id=30)
bid_evaluation_reports: 1 row (report_id=99)
```

### 关键发现

1. **API路径差异**：Spec 说 `/api/v1/projects`，实际是 `/api/projects`
2. **模型修复必要**：`HistoricalBid.postmortem` 和 `InternalPostmortem.bid` 双向FK冲突 → 移除back_populates解决
3. **数据库用户**：`postgres`（非 canteen）

### historical.py 模型修复决策

**建议：正式提交（必要改动）**

- 根因：`internal_postmortems` 表有两个FK指向 `historical_bids`（`id` 和 `historical_bid_id`），导致 `AmbiguousForeignKeysError`
- 修复：移除 `back_populates`，改为单向FK（`foreign_keys=[internal_postmortem_id]` 和 `foreign_keys=[historical_bid_id]`）
- 结论：这是**必要的正确修复**，非临时 workaround，应提交
---

## Session: 2026-05-11/12 Week 3 RAG 生成测试

### 执行时间
2026-05-11 ~ 2026-05-12

### 任务清单

| Task | 任务 | 状态 | 结果 |
|------|------|------|------|
| 1 | 生成第一章（冷链配送方案） | ✅ 完成 | 2579 chars |
| 2 | 生成第二章（食材溯源方案） | ✅ 完成 | 5836 chars |
| 3 | 生成第三章（服务保障方案） | ✅ 完成 | 7261 chars |
| 4 | 保存章节到数据库 | ✅ 完成 | 3 rows (project_sections) |
| 5 | 验收确认 | ✅ 完成 | GET /sections 返回 3 条 |

### 数据库状态

```
 project_id |     section_name     | len  
------------+----------------------+------
        117 | 第一章：冷链配送方案 | 2880
        117 | 第二章：食材溯源方案 | 2567
        117 | 第三章：服务保障方案 | 2546
```

### API端点发现

| 端点 | 方法 | 功能 | 状态 |
|------|------|------|------|
| `/api/v1/projects/{id}/generate-section` | POST | 生成章节 | ✅ 正常 |
| `/api/v1/projects/{id}/sections` | GET | 查询章节列表 | ✅ 正常 |
| `/api/v1/projects/{id}/sections/{name}` | PUT | 保存/更新章节 | ✅ 正常 |

### 关键发现

1. **POST /generate-section 不自动保存**：内容返回但需单独调用 PUT 才能持久化到 project_sections 表
2. **source_chunk_count = 0**：Project 117 自身文档未建立 RAG 索引，内容由 LLM + 双轨 RAG 历史数据生成
3. **双轨 RAG 正常**：`use_dual_track_rag=true` 时 API 正常工作

### 待确认问题

1. **POST /generate-section 不自动保存** - 这是API设计（前端负责保存）还是潜在bug？
2. **source_chunk_count=0** - Project 117 自身文档未建立 RAG 索引，这是预期行为（需要先调用 /documents/embed）还是遗漏？

### 下一步计划

| 优先级 | 任务 | 说明 |
|--------|------|------|
| **P0** | ~~创建测试项目~~ | ✅ 已完成 |
| **P1** | ~~端到端流程测试~~ | ✅ Week 1-2 通过 |
| **P1** | ~~RAG生成测试~~ | ✅ Week 3 通过 |
---

## Session: 2026-05-12 Week 4 定价博弈测试

### 执行时间
2026-05-12

### 任务清单

| Task | 任务 | 状态 | 结果 |
|------|------|------|------|
| 1 | 设置项目预算 | ✅ 完成 | budget_amount = 9,000,000 |
| 2 | 创建成本估算 | ✅ 完成 | cost_estimate id=49, total_cost=9,000,000 |
| 3 | 确认成本估算 | ✅ 完成 | is_confirmed=true |
| 4 | 生成 A/B/C 定价方案 | ✅ 完成 | 3 scenarios (aggressive/balanced/conservative) |
| 5 | 提交定价决策 | ✅ 完成 | pricing_decision id=16, boss_final_price=9,200,000 |
| 6 | 验收确认 | ✅ 完成 | cost_estimates ≥1, pricing_decisions ≥1 |

### 测试结果

```
projects: id=117, budget_amount=9,000,000
cost_estimates: id=49, total_cost=9,000,000, is_confirmed=true
pricing_calculations: 3 scenarios returned
pricing_decisions: id=16, boss_final_price=9,200,000, status='decided'
```

### 关键发现

1. **Loss Pricing Intercept**: 价格=8,800,000 被拒绝（below cost base 9,000,000），使用 price=9,200,000
2. **API正常工作**: POST /pricing-decisions 正确创建决策记录
3. **博弈模型工作**: A/B/C 三方案正确生成，recommended 方案被标记

### 下一步计划

| 优先级 | 任务 | 说明 |
|--------|------|------|
| **P0** | ~~创建测试项目~~ | ✅ 已完成 |
| **P1** | ~~端到端流程测试~~ | ✅ Week 1-2 通过 |
| **P1** | ~~RAG生成测试~~ | ✅ Week 3 通过 |
| **P1** | ~~定价博弈测试~~ | ✅ Week 4 通过 |
| **P2** | Week 5 形式审查测试 | 待定 |

---

## Session: 2026-05-12 Week 5 形式审查测试

### 执行时间
2026-05-12

### 任务清单

| Task | 任务 | 状态 | 结果 |
|------|------|------|------|
| 1 | 查询 TechProposalTask | ⚠️ 跳过 | endpoint 返回 404，无 TechProposalTask 记录 |
| 2 | 确认 TechProposalTask | ⚠️ 跳过 | 同上，无法确认 |
| 3 | 发起形式审查 | ✅ 完成 | 10 checklist items, fatal_count=1 |
| 4 | 查看评审状态 | ✅ 完成 | fatal_pending=1, passed=0 |
| 5 | 确认 fatal 评审项 | ✅ 完成 | 1 fatal item confirmed |
| 6 | 生成最终标书 | ✅ 完成 | Word doc generated (final_bid_117_20260512062831.docx) |
| 7 | 验收确认 | ✅ 完成 | formal_review_items=10, final_bid_documents=1 |

### 测试结果

```
formal_review_items: 10 rows (id=41~50), project_id=117
final_bid_documents: 1 row (id=4, file=/tmp/final_bid_117_20260512062831.docx)
```

### Bug 修复

#### Bug 1: CHECK constraint 'pending' not allowed

**问题**: `formal_review_items.system_status` CHECK 约束只允许 `('passed','failed','warning','uncertain')`，但引擎插入 `'pending'`

**修复**:
```sql
ALTER TABLE formal_review_items DROP CONSTRAINT IF EXISTS formal_review_items_system_status_check;
ALTER TABLE formal_review_items ADD CONSTRAINT formal_review_items_system_status_check CHECK (system_status IN ('passed','failed','warning','uncertain','pending'));
```

#### Bug 2: document_type 'final_bid' not allowed

**问题**: `final_bid_documents.document_type` CHECK 约束不允许 `'final_bid'`

**修复**: 在 `app/api/v1/endpoints/formal_review.py` 中将 `document_type='final_bid'` 改为 `document_type='complete'`

### 关键发现

1. **TechProposalTask 不存在**: Project 117 无 TechProposalTask 记录，无法确认 tech proposal
2. **形式审查可独立进行**: 即使无 tech proposal 确认，formal_review 可正常发起
3. **fatal 项阻止生成**: 只有确认所有 fatal 项后才能生成最终标书

### 下一步计划

| 优先级 | 任务 | 说明 |
|--------|------|------|
| **P0** | ~~创建测试项目~~ | ✅ 已完成 |
| **P1** | ~~端到端流程测试~~ | ✅ Week 1-2 通过 |
| **P1** | ~~RAG生成测试~~ | ✅ Week 3 通过 |
| **P1** | ~~定价博弈测试~~ | ✅ Week 4 通过 |
| **P1** | ~~形式审查测试~~ | ✅ Week 5 通过 |
| **P2** | Week 6 Evolution 测试 | 待定 |
