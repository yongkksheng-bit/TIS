# 系统状态 | TIS 项目龙虾记忆

> **每次启动必读** - Claude 读取此文件获取全局上下文

---

## 【当前总体进度】

**2026-04-15 冷启动接管：全量审计完成，发现关键 Bug + 资产丢失**

**2026-04-14 完成：V3 Seeding Pipeline 重构 + Week3/4 双轨 RAG + 博弈定价完善**

- **V3 Seeding Pipeline**：docx_parser.py（337行，paragraph+table混合解析）+ historical_chunker.py（697行，Filter Chain + LLM洞察）
- **4个企业级防爆补丁**：Exponential Backoff+Jitter / 表格原子emit / has_table标签 / JSONB安全
- **Deep Bid Analyzer**：Map-Reduce DeepSeek API，16章46KB报告，scripts/deep_bid_analysis/
- **Template Reverse Engineer**：DOCX TOC提取，785段落分类，bid_template_structure.json（405KB）
- **Week4 定价博弈**：game_theory.py（market_context注入）+ price_benchmark.py（MarketHeatContext）
- **Week3 双轨 RAG**：retriever.py dual-track + generator.py use_dual_track_rag
- **TrashView.vue**：回收站视图（278行），独立页面
- **⚠️ w013-w018 迁移全部 untracked**：需立即 git add + commit
---

## 【当前正在处理】

**2026-04-14 完成的工作（全局审计 + 记忆更新）：**

1. **V3 Seeding Pipeline 重构** — docx_parser.py + historical_chunker.py V3
2. **4个企业级防爆补丁** — API雪崩防御 / 表格防断裂 / has_table标签 / JSONB兼容
3. **Deep Bid Analyzer** — Map-Reduce DeepSeek API 分析脚本
4. **Template Reverse Engineer** — DOCX TOC 提取 + 段落分类
5. **Week3 双轨 RAG 验证** — retrieve_positive/negative_samples 已实现
6. **Week4 博弈定价验证** — market_context + MarketHeatContext 已实现
7. **龙虾记忆全局更新** — AI_MEMORY.md + .ai_memory/ 全量刷新
8. **w013-w018 迁移文件审计** — 全部 untracked，需尽快提交

---

## 【Docker 环境快照】

```yaml
容器网络: tis_project_tis_net (bridge)
端口映射:
  tis_db:       localhost:5433 → container:5432
  tis_redis:    localhost:6379 → container:6379
  tis_minio:    localhost:9000/9001 → container:9000/9001
  tis_backend:  localhost:8000 → container:8000
  tis_frontend: localhost:3000 → container:80
数据库: canteen_system (postgres:5433, 密码: Syk0215)
Alembic迁移链: w001 ~ w012 (已提交) → w013~w018 (⚠️全部untracked)
DEEPSEEK_API_KEY: (容器环境变量中，模拟模式 source_chunk_count=0)
```

**⚠️ 紧急：w013-w018 迁移全部 untracked**
```bash
# 立即执行
cd D:/tis_project && git add alembic/versions/w013*.py alembic/versions/w014*.py alembic/versions/w015*.py alembic/versions/w016*.py alembic/versions/w017*.py alembic/versions/w018*.py
```

**关键运维命令：**
```bash
# 标准启动（端口 8000）
cd D:/tis_project && docker compose up -d

# 修改后端代码后重建+重启（正确姿势）
docker compose build backend && docker compose up -d backend

# 验证端口
docker ps --format "{{.Names}}\t{{.Ports}}"

# 直连后端 API 验证
curl http://localhost:8000/api/v1/projects/53/evaluations/generate

# E2E 测试（如脚本存在）
python scripts/live_fire_e2e.py
```

---

## 【今日待办】

- [x] V3 Seeding Pipeline 重构（docx_parser.py + historical_chunker.py）
- [x] 4个企业级防爆补丁（API雪崩/表格防断裂/has_table标签/JSONB兼容）
- [x] Deep Bid Analyzer（Map-Reduce DeepSeek API，16章46KB）
- [x] Template Reverse Engineer（DOCX TOC，785段落分类）
- [x] Week3 双轨 RAG 验证（retriever.py + generator.py 已实现）
- [x] Week4 博弈定价验证（game_theory.py + price_benchmark.py 已实现）
- [x] 龙虾记忆全局更新（AI_MEMORY.md + .ai_memory/ 全量刷新）
- [x] w013-w018 迁移文件 git add + commit ✅ (commit 6be65bc)
- [ ] embedder.py 写入 w015 新增的 12 个 metadata 字段
- [ ] 接通真实 ais_service（RAG E2E 验证）

---

## 【短期阻塞点】

| 阻塞点 | 说明 | 状态 |
|--------|------|------|
| w013-w018 迁移 untracked | 6个迁移文件随时可能丢失 | ⚠️ 紧急提交 |
| DeepSeek API 模拟模式 | `source_chunk_count: 0`，返回模拟内容 | 需配置真实 DEEPSEEK_API_KEY |
| embedder.py 未写 w015 字段 | knowledge_chunks 新字段全部为 NULL | 待完成 |
| OCR bid_open_date 未提取 | PDF 解析精度问题 | 非阻塞，属模拟 OCR |

---

## 【最近更新】

| 日期 | 更新摘要 |
|------|----------|
| 2026-04-14 | **V3 Seeding Pipeline + Week3/4 双轨 RAG** - docx_parser.py V3(337行)+historical_chunker.py V3(697行)；4防爆补丁；Deep Bid Analyzer+Template Reverse Engineer；w013-w018迁移审计（全部untracked）；龙虾记忆全局刷新 |
| 2026-03-31 夜 | **Week5 形式审查上线 + 超时/Bug 修复收尾** - formal_review.py 10端点；advance-to-pricing；504三层超时链修复；Pydantic dict[Any]；FastAPI路由顺序；Hard Delete FK防御性删除；confirmAllSections空函数；龙虾记忆自沉积 |
| 2026-03-31 下午 | **Hard Delete 物理删除上线** - 三方联动清理（DB+MinIO+pgvector）；TrashView.vue 回收站界面；恢复/永久销毁/Clear All；R6.1 规范写入 MASTER_SPEC |
| 2026-03-31 上午 | **双重防重 + Week 1/2 重构** - plan_code/agency_project_code 双键体系上线；三重防重端点；ConfirmationView 网格化；EvaluationView 3 按钮操作台；relationship_flag ⊥ generation_mode 解耦；ElMessageBox.confirm 全局升级 |
| 2026-03-30 | **qualification_matcher 假数据修复** - tender_reqs=[] 时正确返回 score=0 + fatal risk；端口拓扑澄清（8000 Docker，8001 Anaconda 孤儿） |
| 2026-03-29 | **E2E 全链路 9/11 PASS** - RAG 生成成功，Boss 审批 RBAC 生效；修复双重 `/api` 前缀、canGenerate 逻辑、Element Plus textarea 检测 |


---

## 【核心架构约束】（永久生效）

### R5：双重防重校验机制（基于真实业务编号）
- **防重优先级**：plan_code > agency_project_code > project_name（兜底）
- **排除状态**：discarded / terminated_by_bost / **is_deleted=True（软删除）** 不参与重复检测
- **409 Payload** 必须包含 `duplicate_code`（含编号类型：采购计划编号 / 采购项目编号）

### 关系标识与生成模式正交原则
- `relationship_flag` 和 `generation_mode` 完全独立，互不决定对方
- 有关系 ≠ 必须走 GUIDED；没关系 ≠ 必须走 AUTO
- 专员根据项目复杂度独立选择生成模式

### 业务阻断必须用 ElMessageBox.confirm
- `ElMessage.error()` → 仅用于非阻断性错误
- `ElMessageBox.confirm()` → 所有需要用户决策的业务阻断（409、权限不足、状态不允许）

### 项目软删除（is_deleted）原则
- `DELETE /projects/{id}` 执行软删除（is_deleted=True），不物理删除记录
- 软删除后的项目不参与任何重复检测，允许同名项目重新创建
- `GET /projects` 和 `GET /{id}` 均过滤 `is_deleted=False`
- `GET /projects/trash` 列出所有 is_deleted=True 项目
- `POST /projects/{id}/restore` 从回收站恢复（is_deleted=False）
- `DELETE /projects/{id}/hard-delete` 物理删除，触发三方联动清理

### 物理删除三方联动清理规范（已实现）
- 步骤1：MinIO 删除 `project-{id}/` 前缀对象（非阻塞，失败记 -1）
- 步骤2：pgvector 删除 `knowledge_chunks WHERE source_project_id=id`（非阻塞，失败记 -1）
- 步骤3：PostgreSQL DELETE + CASCADE 自动清理关联行
- MinIO/pgvector 失败不影响 DB 事务提交
- 删除向量数据时用 `project_id` 精确过滤，严禁误删其他项目数据

### 算力异构架构（永久锁定）
- **Embedding**：BGE-Small on GPU (FP16) → `AIServiceEmbedder` 调用 `http://ai_service:8000/embed`
- **Reranking**：BGE-Reranker-Base on CPU (FP32) → `CrossEncoder(..., device="cpu")`
- **Text Generation**：DeepSeek `/chat/completions`（仅用于 LLM 生成，绝不用于嵌入任务）
- 严禁将 Embedding/Reranking 任务路由到外部 DeepSeek Embeddings API

### RAG 长文档处理（12,000 字符截断 + 4 维度法务 Prompt）
- 超过 12,000 字符的文档在 RAG 检索前截断
- 资质提取采用 4 维度法务级 Prompt：政采法22条 / 军采特殊资质 / 实质性承诺★ / 废标条款
- RAG 检索是处理长文档（>12,000 chars）的唯一路径

### 前端请求超时配置
- axios 全局 `timeout: 300000`（300 秒），配合 Nginx 300s 和 Uvicorn --timeout-keep-alive 300，三层统一

---

## 【下次启动时上下文】

1. Docker 启动：`cd D:/tis_project && docker compose up -d`
2. 验证后端端口：`docker ps --format "{{.Names}}\t{{.Ports}}"` → 确认为 `localhost:8000`
3. 如遇 backend 报 `host db not found`：执行 `docker network connect tis_project_tis_net tis_backend`
4. E2E 测试：`python scripts/live_fire_e2e.py`
5. 如需重建后端：`docker compose build backend && docker compose up -d backend`

_下次启动时从此文件读取上下文_
