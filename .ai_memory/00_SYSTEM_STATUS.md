# 系统状态 | TIS 项目龙虾记忆

> **每次启动必读** - Claude 读取此文件获取全局上下文

---

## 【当前总体进度】

**2026-03-31 重大更新：双重防重 + Week 1/2 重构 + 关系标识正交化**

- `plan_code` + `agency_project_code` 双键防重体系已上线（w010 迁移 + 三重校验端点）
- `relationship_flag` 从 Week 1 迁移至 Week 2，与 `generation_mode` 完全解耦
- 专员越级放行（direct_execute）已实现，3 动作审批模型已上线
---

## 【当前正在处理】

**2026-03-31 完成的工作：**

1. **新增 Alembic 迁移 w010**：`plan_code` + `agency_project_code` 添加到 `projects` 和 `tender_documents` 表
2. **parser.py 正则提取**：采购计划编号（`441301-2025-03605`）、采购项目编号（`HZJJ-2025118号`）
3. **三重防重端点** `POST /api/projects`：plan_code → agency_project_code → project_name，409 返回 `duplicate_code` 含编号类型
4. **ConfirmationView 双列网格**：el-row/el-col 紧凑布局，删除 relation_identifier + differentiation_guidance
5. **EvaluationView 3 按钮操作台**：`submit_to_boss` / `direct_execute` / `terminate` 三动作
6. **关系标识强制回滚**：`PUT /{id}/relationship` + `process_relationship_change()` — Week 3+ 变更触发 rollback
7. **ElMessageBox.confirm**：ProjectUploadView 409 处理升级为阻断性弹窗
8. **文档更新**：MASTER_SPEC 第 4/5/6/7 章 + ARCHITECTURE_AUDIT D-012

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
Alembic迁移链: w001 → ... → w007(w009) → w008 → w009 → w010
DEEPSEEK_API_KEY: (容器环境变量中，模拟模式 source_chunk_count=0)
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

# E2E 测试
python scripts/live_fire_e2e.py
```

---

## 【今日待办】

- [x] 双重防重键（plan_code / agency_project_code）模型 + 迁移
- [x] parser.py 正则提取采购计划编号 + 采购项目编号
- [x] 三重防重端点 + 丰富 409 Payload
- [x] ConfirmationView 双列网格布局
- [x] EvaluationView 3 按钮操作台 + 强制回滚
- [x] ElMessageBox.confirm 处理 409
- [x] 文档更新（MASTER_SPEC、ARCHITECTURE_AUDIT、AI_MEMORY）
- [x] 龙虾记忆归档（本次）

---

## 【短期阻塞点】

| 阻塞点 | 说明 | 状态 |
|--------|------|------|
| DeepSeek API 模拟模式 | `source_chunk_count: 0`，返回模拟内容 | 需配置真实 DEEPSEEK_API_KEY |
| OCR bid_open_date 未提取 | PDF 解析精度问题 | 非阻塞，属模拟 OCR |
| PDF iframe 预览未加载 | Vue/iframe 时序问题 | 非阻塞，不影响流程 |

---

## 【最近更新】

| 日期 | 更新摘要 |
|------|----------|
| 2026-03-31 | **双重防重 + Week 1/2 重构** - plan_code/agency_project_code 双键体系上线；三重防重端点；ConfirmationView 网格化；EvaluationView 3 按钮操作台；relationship_flag ⊥ generation_mode 解耦；ElMessageBox.confirm 全局升级 |
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
- 硬删除（物理删除）预留 `_hard_delete_project()` 钩子，待未来实现

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
- axios 全局 `timeout: 120000`（120 秒），适应大 PDF 解析 + GPU 向量计算

---

## 【下次启动时上下文】

1. Docker 启动：`cd D:/tis_project && docker compose up -d`
2. 验证后端端口：`docker ps --format "{{.Names}}\t{{.Ports}}"` → 确认为 `localhost:8000`
3. 如遇 backend 报 `host db not found`：执行 `docker network connect tis_project_tis_net tis_backend`
4. E2E 测试：`python scripts/live_fire_e2e.py`
5. 如需重建后端：`docker compose build backend && docker compose up -d backend`

_下次启动时从此文件读取上下文_
