# TIS 项目 — AI 唤醒记忆 (Claude Memory)

> 上次对话结束时间：2026-04-14（全局审计快照）
> 状态：**V3 Seeding Pipeline 重构完成 + Week3/4 双轨 RAG + 博弈定价上线 + 历史数据层完善**

---

## 🔴 V3 Seeding Pipeline 重构（2026-04-14 新增）

### 重构背景：160+表格数据全部丢失

原始 `docx_parser.py` 只解析 `doc.paragraphs`，**160+张表格全部丢失**。原始 `historical_chunker.py` 无 boilerplate 过滤、无 LLM 洞察、无表格处理。

### 重构成果：docx_parser.py V3（337行）

**核心突破：文档物理顺序遍历（paragraph + table 混合顺序）**

```python
# 遍历 document.element.body 子元素，按物理位置排序
for child in doc.element.body:
    tag = child.tag.split("}")[-1]
    if tag == "p":
        text = _extract_para_text(child)  # 段落提取
        blocks.append(Block(block_type="paragraph", content=text))
    elif tag == "tbl":
        tbl_obj = _find_table_by_element(doc, child)  # python-docx Table 对象
        extractor = TableBlockExtractor.from_docx_table(tbl_obj)
        if extractor.is_meaningful():
            md_lines = extractor.to_markdown_lines()
            blocks.append(Block(block_type="table", content="\n".join(md_lines)))
```

**输出变更：** `DOCXParseResult` 新增 `blocks: list[Block]` 字段（保留段落+表格原始顺序），`paragraphs` 保持向后兼容。

**TableBlockExtractor 关键设计：**
- 跨行合并单元格（vMerge）→ 输出为空字符串，保留列对齐
- 全空行自动过滤
- `is_meaningful(min_content_chars=5)` 过滤无意义装饰表格

### 重构成果：historical_chunker.py V3（697行）

**三层过滤架构（Filter Chain）：**

```
DOCX文档块（paragraphs + tables）
    │
    ▼
Layer 0: 类型过滤
    ├─ paragraph → 原样进入 Layer 1
    └─ table     → 跳过boilerplate，整体进入 Layer 3
    │
    ▼
Layer 1: Boilerplate 过滤（49个关键词）
    ├─ 静态模板（授权/承诺函/证明/证书/封面/扉页...）→ 直接丢弃
    └─ 通过 → 进入 Layer 2
    │
    ▼
Layer 2: 聚类 + 滑动窗口（chunk_size=600, overlap=80）
    ├─ 按 heading 聚合成「章」
    └─ 每章按 500 字滑动窗口切分
    │
    ▼
Layer 3: LLM 洞察提取（enable_llm_insights=True 时激活）
    └─ 仅对动态段落调用 DeepSeek，提取 {core_pain_points, technical_indicators, competitive_advantages}
```

**4个企业级防爆补丁：**

| 补丁 | 实现 | 效果 |
|------|------|------|
| 补丁1: API并发雪崩防御 | `tenacity` Exponential Backoff + Full Jitter + `Semaphore(max_concurrency=5)` | 529 限流永不重爆 |
| 补丁2: Markdown表格安全防断裂 | `block_type=="table"` 时跳过 sliding window，原子 emit | 160+表格绝不切断 |
| 补丁3: 特异性标签注入 | `has_table: True/False` 写入 `chunk_metadata` | RAG 精准召回资质表/报价表 |
| 补丁4: JSONB兼容性保证 | `Block.__slots__` + `ChunkDict.__slots__` + 纯Python类型 | PostgreSQL JSONB 无缝映射 |

**LLM 洞察提取 API 调用（Patch 1 核心）：**
```python
# Exponential Backoff + Full Jitter
wait = (2 ** attempt) * 1.0 * random.random()  # 随机抖动
time.sleep(wait)
# HTTP 529 → 重试；5xx → 重试；网络异常 → 重试
```

**Boilerplate 关键词（49个）：**
授权、承诺函、证明、证书、复印件、盖章、资质、营业执照、法人代表、委托人、身份证、授权委托书、声明、声明书、公证书、投标函、投标文件、封面、扉页、目录、密封、签署、日期、编号、文件格式...

**Generative 关键词（40个）：**
服务方案、配送方案、应急方案、保障方案、质量保障、食品安全、卫生管理、人员配置、培训考核、监督机制、管理制度、操作规程、岗位职责...

### Untracked 迁移文件（w013-w018，全部存在于 alembic/versions/）

| 迁移 | 内容 | 状态 |
|------|------|------|
| w013 | `project_sections` 表（UQ: project_id+section_name，FK CASCADE） | untracked |
| w014 | `specialist_price` 字段添加到 projects 表 | untracked |
| w015 | `knowledge_chunks` 12个新字段（source_type, source_id, win_signal, scoring_dimension_tags ARRAY, region_tags ARRAY, is_price_sensitive, token_count...） | untracked |
| w016 | `historical_tenders` 表（采购计划编号、预算、中标单位、日期） | untracked |
| w017 | `historical_bids` 表（报价、中标情况、历史tender_id、price_gap） | untracked |
| w018 | `internal_postmortems` 表（流标原因分析、中标DNA、废标陷阱） | untracked |

**⚠️ 警告：** w013-w018 迁移文件全部 untracked，需尽快 `git add` 并 commit 防止丢失。

---

## 🔴 冷启动断层记录（2026-04-15 新增）

### P0 级：E2E 测试脚本被物理删除

- **Type**: 故障
- **Score**: 1.0
- **Date**: 2026-04-14 夜间（断电前）
- **Status**: Active
---
**`scripts/live_fire_e2e.py` 及其配套脚本已被删除：**
- `scripts/live_fire_e2e.py` — Python E2E 测试主脚本 ⚠️
- `scripts/health_check.bat` / `scripts/health_check.sh`
- `scripts/prepare_test_project.py`
- `scripts/seed_standard_certs.py`
- `scripts/simulate_deploy.sh`
- `scripts/wipe_dbs.py`
- `update_aimemory.py`

**当前替代：** `scripts/e2e/` 目录存在 Playwright (Node.js) 框架，但测试内容与原 Python 脚本不同。

**紧急恢复命令：**
```bash
git checkout HEAD -- scripts/live_fire_e2e.py scripts/health_check.bat scripts/health_check.sh scripts/prepare_test_project.py scripts/seed_standard_certs.py scripts/simulate_deploy.sh scripts/wipe_dbs.py update_aimemory.py
```

### P1 级：status.json.bak 为过期陈旧备份

- **Type**: 状态不一致
- **Score**: 0.9
- **Date**: 2026-04-14
- **Status**: Active
---
`status.json.bak` 内容为 `phase: "init"`（pipeline 运行前状态），而非运行后的正确快照。`status.json` 正确显示 `phase: "done"` + `total_chunks_written: 2329`（Pipeline 已成功完成）。

**不得使用 `status.json.bak` 进行任何恢复操作。**

### P2 级：E2E 测试框架迁移未完成

- **Type**: 架构未完成
- **Score**: 0.8
- **Date**: 2026-04-14 夜间
- **Status**: Active
---
`scripts/e2e/` 已存在 Playwright (Node.js) 测试框架，但：
1. 原 `live_fire_e2e.py` Python E2E 脚本已被删除
2. 新 Playwright 测试内容与原脚本不对等
3. `AI_MEMORY.md` 中记录的 E2E 命令 `python scripts/live_fire_e2e.py` 已失效

**下一步：** 确认 Playwright E2E 测试内容覆盖度，或恢复 Python 脚本。

---

## 🔴 Week5 + 二次投标 + ProjectSection 持久化（2026-04-01 新增）

### 新建数据库表 `project_sections`（迁移 w013）

```python
# app/models/project_section.py
class ProjectSection(Base, TimestampMixin):
    __tablename__ = "project_sections"
    __table_args__ = (
        UniqueConstraint('project_id', 'section_name', name='uq_project_section_name'),
    )
    # id, created_at, updated_at — 继承自 TimestampMixin
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    section_name: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    project: Mapped["Project"] = relationship("Project", back_populates="sections")
```

**关键约束：** `(project_id, section_name)` 联合唯一，防止同一项目内重复章节名。

---

### 新建端点 `POST /api/projects/{id}/clone`

**两种克隆路径：**

| clone_type | parent_project_id | plan_code | 命名规则 |
|---|---|---|---|
| `rebid`（流标重投） | = source_id | 继承老项目 | `xxx - 重投` |
| `annual_renewal`（新一期） | = NULL | 来自请求体（最新解析） | `xxx - 2026` |

**防重命名链：** `xxx - 重投` → `xxx - 重投 (2)` → `xxx - 重投 (3)` 自动排重。

**资产复制：** 查询 `ProjectSection WHERE project_id=source_id`，完整复制内容到新项目。

---

### 改造端点 `PUT /api/v1/projects/{id}/sections/{section_name}`

- **Upsert 机制**：INSERT ON CONFLICT DO UPDATE（强制覆盖旧内容）
- **非阻塞**：`ProjectSection` 保存失败不影响内存内容，告警而非报错
- `upserted: true` = 本次为新插入，`upserted: false` = 更新

### 改造端点 `GET /api/v1/projects/{id}/sections`

- **优先路径**：`ProjectSection` 表（新权威存储，2026-04-01+）
- **兜底路径**：`TechProposalTask.generated_content` JSON（旧项目兼容）

---

### 前端右键菜单（ProjectCard.vue）

右键卡片弹出 `el-dropdown` 菜单，两个选项：
- **克隆：流标重投** → 直接调 `POST /api/projects/{id}/clone {rebid}` → 跳转新项目确认页
- **克隆：新一期招标** → 存 `pendingClone` 状态 → 跳转上传页 → 解析完自动调 clone API

---

### 前端 ProjectUploadView.vue 双重改造

1. **409 弹窗标题**：改为 `"项目重复"`（删除原" — 二次投标确认"字样）
2. **重试逻辑**：从调 `force_retender` 改为调 `POST /v1/projects/{id}/clone {rebid}`
3. **pending clone 处理**：上传成功后，如 `projectStore.pendingClone.cloneType === 'annual_renewal'`，自动从解析结果提取年份 → 调 clone API → 跳转新项目确认页

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

**测试脚本：** `scripts/e2e/` (Playwright-based Node.js E2E) ⚠️ `scripts/live_fire_e2e.py` 已删除
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

## 今日重大修复 (2026-04-01)

### Week5 + 二次投标克隆 + ProjectSection 持久化

**新增文件：**
- `alembic/versions/w013_create_project_sections.py` — `project_sections` 表（uq_project_section_name 联合唯一，FK CASCADE）
- `app/models/project_section.py` — `ProjectSection(Base, TimestampMixin)` 模型
- `app/api/v1/endpoints/formal_review.py` — Week5 形式审查 10 端点 + advance-to-pricing

**POST /api/projects/{id}/clone 核心逻辑：**
```python
# rebid: 继承 plan_code, parent_project_id=source_id, name="xxx - 重投"
# annual_renewal: plan_code 来自请求体, parent_project_id=NULL, name="xxx - 2026"
new_project = Project(..., is_retender=(clone_type == "rebid"), parent_project_id=...)
# 复制 ProjectSection 记录
for sec in db.query(ProjectSection).filter(project_id=source_id).all():
    db.add(ProjectSection(project_id=new_project.id, section_name=sec.section_name, content=sec.content))
```

**PUT /api/v1/projects/{id}/sections/{section_name}：**
- Upsert 机制：INSERT ON CONFLICT DO UPDATE（强制覆盖）
- 非阻塞：保存失败不阻断内存内容，只告警

**GET /api/v1/projects/{id}/sections 读路径：**
1. `ProjectSection` 表（新权威）→ 2. `TechProposalTask.generated_content` JSON（旧兼容）

**前端右键菜单（ProjectCard.vue）：**
- `@contextmenu` 触发 `el-dropdown`，两个选项对应不同 clone_type
- `pendingClone` 状态存储在 projectStore，跨页面传递

**Bug 修复（本次新增）：**
- FastAPI 路由顺序：`/trash`、`/clone` 静态路径必须在 `/{project_id}` 之前
- `ProjectSection` 必须定义 `relationship "project"` + `back_populates` 否则 SQLAlchemy mapper 初始化失败
- TypeScript `el-dropdown @command` 类型：`cmd as 'rebid' | 'annual_renewal'`
- CSS `z-index: 10` 写成了 `z-index 10`（缺少冒号）

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

### 🔴 FastAPI 路由顺序陷阱
**症状**：`GET /api/projects/trash` 返回 404
**根因**：`/{project_id}` 动态路由定义在 `/trash` 静态路径之前，"trash" 被当作 project_id
**修复**：所有静态路径（`/trash`、`/clear-trash`、`/clone`）必须定义在 `/{project_id}` **之前**
**诊断**：`docker compose exec backend python -c "from app.api.v1.endpoints.projects import router; [print(r.methods, r.path) for r in router.routes]"`

### 🔴 Docker 重建后代码未生效
**症状**：修改了 Vue 或 Python 文件，刷新浏览器但界面没有变化
**根因**：Docker 容器使用镜像层缓存代码，文件修改不会自动同步
**修复**：每次代码修改后必须 `docker compose build backend && docker compose up -d backend`（前端：`docker compose build frontend`）

### 🔴 批量删除中 Detached ORM 对象
**症状**：`clear_trash` 某条失败后，`project.id` 抛出 `PendingRollbackError`
**根因**：事务回滚后 ORM 对象从 session 分离，访问属性报错
**修复**：在 try 块**之前**捕获 `pid = project.id`，不在回滚后访问对象属性

### 🔴 504 Timeout 三层链同时不足
**症状**：DeepSeek LLM 生成长文本 > 60s 返回 504
**根因**：Nginx `proxy_read_timeout=60s` 先于 axios 120s 爆掉；Uvicorn 无 `--timeout-keep-alive`
**修复（三层全部 300s）**：
- `frontend/nginx.conf`：`proxy_read_timeout 300s`
- `app/Dockerfile`：`--timeout-keep-alive 300`
- `frontend/src/api/client.ts`：`timeout: 300000`

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
│   │   ├── projects.py            ← upload, confirm-parsing, confirmation-data,
│   │   │                             三重防重, POST /clone (rebid/annual_renewal)
│   │   │                             DELETE /trash, POST /clear-trash, projects_clear_trash_patch
│   │   ├── evaluations.py          ← specialist_approve（三动作）
│   │   ├── rag.py                  ← generate-section, GET/PUT /sections
│   │   ├── formal_review.py        ← Week5 形式审查 10 端点 + advance-to-pricing
│   │   ├── pricing.py              ← Week4 定价博弈端点 (454行)
│   │   ├── documents.py, review.py ← 辅助端点
│   │   └── projects_clear_trash_patch.py ← 回收站清空补丁
│   ├── models/
│   │   ├── project.py              ← sections relationship (back_populates)
│   │   ├── project_section.py      ← ProjectSection 表（w013）
│   │   ├── knowledge_chunk.py      ← w015 扩展 12 个新字段
│   │   ├── historical.py           ← historical_tenders/bids 表 (w016/w017)
│   │   ├── formal_review.py        ← FormalReviewItem 表
│   │   ├── pricing.py              ← PricingRecord 表
│   │   └── enums.py, approval.py, discarded.py, ...
│   ├── core/
│   │   ├── week1_document/
│   │   │   ├── parser.py           ← OCR + 字段抽取 + plan_code 正则
│   │   │   ├── qualification_extractor.py ← LLM 4维度法务资质提取
│   │   │   ├── cert_matcher.py, confirmation_service.py, ...
│   │   ├── week2_evaluation/
│   │   │   ├── evaluation_engine.py, approval_service.py
│   │   │   ├── qualification_matcher.py, time_evaluator.py, ...
│   │   ├── week3_rag/
│   │   │   ├── retriever.py        ← dual-track 检索 (421行)
│   │   │   │     retrieve_positive_samples() + retrieve_negative_samples()
│   │   │   ├── generator.py        ← dual-track RAG 生成 (316行)
│   │   │   │     use_dual_track_rag + build_chunk_context()
│   │   │   ├── text_chunker.py     ← HistoricalChunker V3 (342行)
│   │   │   ├── embedder.py         ← AIServiceEmbedder (109行)
│   │   │   ├── llm_mock.py         ← get_llm() 工厂 + RealDeepSeekLLM
│   │   │   ├── prompt_builder.py   ← prompt 构建
│   │   │   └── prompt_templates.py ← Week3 prompt 模板
│   │   ├── week4_pricing/
│   │   │   ├── price_benchmark.py  ← MarketHeatContext (246行)
│   │   │   ├── game_theory.py      ← market_context 注入博弈 (298行)
│   │   │   ├── cost_engine.py, intercept_rules.py
│   │   ├── week5_formal_review/
│   │   │   ├── formal_review_engine.py ← 形式审查引擎 (564行)
│   │   │   ├── word_generator.py, pdf_highlighter.py
│   │   └── week6_review/
│   │       ├── review_engine.py, revival_engine.py
│   │   └── hard_delete/
│   │       └── minio_cleanup.py    ← 物理删除三方联动
├── frontend/src/
│   ├── components/
│   │   ├── ProjectCard.vue        ← 右键菜单 + pendingClone
│   │   ├── TrashView.vue          ← 回收站视图 (278行)
│   │   └── RebidAlertDialog.vue, StatusBadge.vue
│   ├── stores/
│   │   └── projectStore.ts        ← pendingClone 状态管理
│   └── views/
│       ├── ConfirmationView.vue   ← 双列网格
│       ├── EvaluationView.vue      ← 三按钮操作台
│       ├── ProjectUploadView.vue   ← 409 弹窗 + clone 处理
│       ├── TechProposalView.vue    ← 生成 + Upsert
│       ├── PricingView.vue         ← Week4 定价博弈
│       ├── FormalReviewView.vue    ← Week5 形式审查
│       ├── FinalOutputView.vue, BusinessProposalView.vue
│       ├── DashboardView.vue, ReviewView.vue, TrashView.vue
├── alembic/versions/
│   ├── w001 ~ w012                 ← tracked (已提交)
│   ├── w013_create_project_sections.py    ← untracked (w013)
│   ├── w014_add_specialist_price.py        ← untracked (w014)
│   ├── w015_expand_knowledge_chunks.py     ← untracked (w015)
│   ├── w016_create_historical_tenders.py   ← untracked (w016)
│   ├── w017_create_historical_bids.py      ← untracked (w017)
│   └── w018_create_internal_postmortems.py ← untracked (w018)
├── ai_service/
│   ├── main.py              ← GPU FP16 + CPU FP32
│   └── requirements.txt     ← transformers<=4.38.0
└── scripts/
    ├── deep_bid_analysis/
    │   ├── deep_bid_analyzer.py      ← Map-Reduce DeepSeek API 分析 (223行)
    │   ├── template_reverse_engineer.py ← DOCX TOC + 模板逆向 (535行)
    │   ├── bid_template_structure.json ← 785 个段落分类 (405KB)
    │   └── V2_bid_assembly_logic.md  ← 投标组装逻辑 (188KB)
    └── seeding/
        ├── parsers/
        │   ├── docx_parser.py         ← V3: paragraph+table 混合解析 (337行)
        │   └── pdf_parser.py
        ├── chunkers/
        │   └── historical_chunker.py  ← V3: Filter Chain + LLM 洞察 (697行)
        ├── loaders/
        ├── embedders/
        └── run_import.py              ← 导入入口
```

---

## 短期路线图

- [x] ai_service 微服务异构计算架构（GPU FP16 + CPU FP32 Reranker）— ✅ 已稳定运行
- [x] Bug-011 架构修复（DeepSeekEmbedder → AIServiceEmbedder）— ✅ 已完成
- [x] 前端 axios 超时提升至 300s（504 根因修复）— ✅ 已完成
- [x] 软删除 is_deleted 上线（w011+w012）— ✅ 已完成
- [x] Week5 形式审查（formal_review.py 10 端点）— ✅ 已完成
- [x] 二次投标克隆 API（POST /clone + rebid/annual_renewal）— ✅ E2E 验证通过
- [x] ProjectSection 持久化（w013 + Upsert + GET 读路径）— ✅ E2E 验证通过
- [x] 前端右键菜单 + pendingClone 状态管理 — ✅ 已完成
- [x] 409 弹窗标题改为"项目重复" + 重试改 clone API — ✅ 已完成
- [x] 龙虾记忆自沉积（04_FACTS + 02_CAUSALITY + 00_SYSTEM_STATUS + work_logs）— ✅ 已完成
- [x] V3 Seeding Pipeline 重构（docx_parser.py + historical_chunker.py）— ✅ 2026-04-14
- [x] Deep Bid Analyzer（Map-Reduce DeepSeek API，16章 46KB 报告）— ✅ 2026-04-14
- [x] Template Reverse Engineer（DOCX TOC 提取，785段落分类）— ✅ 2026-04-14
- [x] Week4 定价博弈（game_theory.py market_context + price_benchmark.py）— ✅ 2026-04-14
- [x] Week3 双轨 RAG（retrieve_positive/negative_samples + use_dual_track_rag）— ✅ 2026-04-14
- [x] TrashView.vue 回收站视图（278行）— ✅ 已完成
- [ ] 接通真实 DeepSeek LLM（source_chunk_count > 0，USE_MOCK_LLM=false）
- [ ] w013-w018 迁移文件 `git add` + commit（当前全部 untracked）
- [ ] 历史标书批量注入：`python scripts/ingest_tenders.py` 灌入 10 份真实标书
- [ ] embedder.py 写入 w015 新增的 12 个 metadata 字段
- [ ] 接通真实 ais_service（RAG embedding + reranking E2E 验证）

