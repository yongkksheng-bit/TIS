# TIS 最终验证计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:systematic-debugging (for smoke test execution) and superpowers:test-driven-development (for regression tests). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 验证 TIS 系统端到端工作流完整性，建立每日集成检查点，确保系统可完整跑通且无回归。

**Architecture:** 基于 FastAPI 后端 + Vue 前端，使用 pytest 进行自动化回归测试，curl 命令执行手动冒烟测试，全程记录不修改业务代码。

**Tech Stack:** FastAPI, PostgreSQL/pgvector, Vue 3, pytest, curl

---

## 冒烟测试路径

### 路径A：直接执行（specialist直接执行）

1. `POST /api/projects` → 创建项目
2. `POST /api/projects/{id}/upload` → 上传PDF
3. `GET /api/projects/{id}/confirmation-data` → 获取OCR数据
4. `POST /api/projects/{id}/confirm-parsing` → 确认解析（17项）
5. `POST /api/v1/projects/{id}/evaluations/generate` → 生成评估
6. `POST /api/v1/evaluations/{id}/approve` → action=direct_execute
7. `POST /api/v1/projects/{id}/generate-section` → 生成章节
8. `PUT /api/v1/projects/{id}/sections/{name}` → 保存章节
9. `POST /api/projects/{id}/advance-to-pricing` → 推进定价（**注意：无/v1前缀**）
10. `POST /api/v1/projects/{id}/pricing-decisions` → 提交定价
11. `POST /api/v1/projects/{id}/checklists/init` → 初始化审查
12. `POST /api/v1/projects/{id}/complete` → 完成审查

**预期最终状态:** completed

---

### 路径B：老板审批（specialist提交→boss审批）

1-5: 同路径A

6a. `POST /api/v1/evaluations/{id}/approve` → action=submit_to_boss (role=specialist)
   → 状态变为 pending_boss_approval

6b. `POST /api/v1/evaluations/{id}/approve` → role=boss, action=approve, override_reason=...
   → 状态变为 generating_documents

7-12: 同路径A

**预期最终状态:** completed

---

## 冒烟测试前提条件

### 环境检查
- Docker 服务运行中：`docker compose ps` 确认所有容器 healthy
- 后端 API 可达：`curl http://localhost:8000/docs` 返回 200
- 前端 Web 可达：`curl http://localhost:3000` 返回 200
- 数据库可连接：测试文件使用内存 SQLite，不依赖外部 DB

### 测试数据准备
- 需要一个真实 PDF 测试文件（招标文件 .docx 或 .pdf）
- 测试用户：系统已有 Demo 用户（id=1）
- 项目将使用新创建的测试项目（id 自增）

---

## 冒烟测试：黄金路径 12 步

### Step 1: 创建项目
**Method:** POST /api/projects
**curl:**
```bash
curl -s -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"project_name":"2026_集成验证测试_测试项目","project_type":"service","region":"广东省广州市","budget_amount":5000000}'
```
**预期:** HTTP 200, `data.id` 字段存在，`data.status === "uploaded"`
**失败处理:** 立即停止，记录错误

### Step 2: 上传 PDF
**Method:** POST /api/projects/{project_id}/upload
**依赖:** Step 1 成功，拿到 `project_id`
**curl:**
```bash
curl -s -X POST http://localhost:8000/api/projects/{project_id}/upload \
  -F "file=@test_tender.pdf"
```
**预期:** HTTP 200, `data.project_id === project_id`, `data.status === "upload_status=success"`
**失败处理:** 立即停止，记录错误

### Step 3: 获取 OCR 确认数据
**Method:** GET /api/projects/{project_id}/confirmation-data
**curl:**
```bash
curl -s http://localhost:8000/api/projects/{project_id}/confirmation-data
```
**预期:** HTTP 200, `data.pending_review_count` 表示待确认字段数
**失败处理:** 如果 404，可能解析未完成，等待后重试（最多 3 次，间隔 10s）

### Step 4: 确认解析（提交确认）
**Method:** POST /api/projects/{project_id}/confirm-parsing
**注意:** 需要提供所有 extraction_id 的确认（17项）
**curl:**
```bash
curl -s -X POST http://localhost:8000/api/projects/{project_id}/confirm-parsing \
  -H "Content-Type: application/json" \
  -d '{
    "confirmations": [
      {"extraction_id": XX, "action": "confirm"},
      ... (17项)
    ],
    "project_name":"测试项目",
    "bid_open_date":"2026-06-30",
    "owner_unit":"测试单位",
    "budget_amount":5000000,
    "region":"广东省广州市",
    "project_type":"service"
  }'
```
**预期:** HTTP 200, `data.status === "confirmed"`, `data.project_status === "evaluating"`
**失败处理:** 立即停止，记录错误

### Step 5: 生成初筛报告
**Method:** POST /api/v1/projects/{project_id}/evaluations/generate
**curl:**
```bash
curl -s -X POST http://localhost:8000/api/v1/projects/{project_id}/evaluations/generate \
  -H "Content-Type: application/json" \
  -d '{}'
```
**预期:** HTTP 200, `data.report_id` 存在
**失败处理:** 立即停止，记录错误

### Step 6: 审批通过（Specialist 审批）
**Method:** POST /api/v1/evaluations/{report_id}/approve

**路径A - direct_execute:**
```bash
curl -s -X POST http://localhost:8000/api/v1/evaluations/{report_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"action":"direct_execute","generation_mode":"AUTO","user_id":1,"role":"specialist"}'
```
→ 状态变为 generating_documents

**路径B - submit_to_boss + boss_approve:**
```bash
# 6a: specialist 提交给 boss
curl -s -X POST http://localhost:8000/api/v1/evaluations/{report_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"action":"submit_to_boss","generation_mode":"AUTO","user_id":1,"role":"specialist"}'
# → 状态变为 pending_boss_approval

# 6b: boss 审批
curl -s -X POST http://localhost:8000/api/v1/evaluations/{report_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"action":"approve","generation_mode":"AUTO","user_id":1,"role":"boss","override_reason":"测试审批通过"}'
# → 状态变为 generating_documents
```

**预期:** HTTP 200
**失败处理:** 立即停止，记录错误

### Step 7: 生成技术标章节
**Method:** POST /api/v1/projects/{project_id}/generate-section
**curl:**
```bash
curl -s -X POST http://localhost:8000/api/v1/projects/{project_id}/generate-section \
  -H "Content-Type: application/json" \
  -d '{"section_name":"第一章：项目理解","generation_mode":"auto"}'
```
**预期:** HTTP 200, `data.content` 存在且长度 > 0
**失败处理:** 立即停止，记录错误

### Step 8: 保存章节
**Method:** PUT /api/v1/projects/{project_id}/sections/{section_name}
**curl:**
```bash
curl -s -X PUT "http://localhost:8000/api/v1/projects/{project_id}/sections/第一章：项目理解" \
  -H "Content-Type: application/json" \
  -d '{"section_name":"第一章：项目理解","content":"[生成的内容]","mode":"auto"}'
```
**预期:** HTTP 200 或 201
**失败处理:** 继续到 Step 9（此步非严格依赖）

### Step 9: 推进到定价
**Method:** POST /api/projects/{project_id}/advance-to-pricing
**注意:** 使用 `/api/projects/` 而非 `/api/v1/projects/`
**curl:**
```bash
curl -s -X POST http://localhost:8000/api/projects/{project_id}/advance-to-pricing
```
**预期:** HTTP 200, 项目状态变为 `awaiting_pricing`
**失败处理:** 立即停止，记录错误

### Step 10: 提交定价决策
**Method:** POST /api/v1/projects/{project_id}/pricing-decisions
**前置条件:** 需要已确认的成本估算（cost estimate with `is_confirmed=true`）
**curl:**
```bash
# 先创建成本估算
curl -s -X POST http://localhost:8000/api/v1/projects/{project_id}/cost-estimates \
  -H "Content-Type: application/json" \
  -d '{"food_cost":3000000,"logistics_cost":500000,"labor_cost":800000,"management_cost":500000,"estimate_reason":"测试成本"}'

# 确认成本估算 (获取 estimate_id 后)
curl -s -X POST http://localhost:8000/api/v1/cost-estimates/{estimate_id}/confirm \
  -H "Content-Type: application/json" \
  -d '{"confirm":true}'

# 提交定价决策
curl -s -X POST http://localhost:8000/api/v1/projects/{project_id}/pricing-decisions \
  -H "Content-Type: application/json" \
  -d '{"boss_final_price":5500000,"boss_decision_reason":"合理利润定价","action_type":"normal"}'
```
**预期:** HTTP 200, 项目状态变为 `awaiting_review`
**失败处理:** 立即停止，记录错误

### Step 11: 初始化形式审查
**Method:** POST /api/v1/projects/{project_id}/checklists/init
**curl:**
```bash
curl -s -X POST http://localhost:8000/api/v1/projects/{project_id}/checklists/init
```
**预期:** HTTP 200, `data.itemsCreated` > 0
**失败处理:** 立即停止，记录错误

### Step 12: 完成形式审查
**Method:** POST /api/v1/projects/{project_id}/complete
**前置条件:** 所有 fatal 项已确认（或 fatalCount=0）
**curl:**
```bash
curl -s -X POST http://localhost:8000/api/v1/projects/{project_id}/complete
```
**预期:** HTTP 200, 项目状态变为 `completed`
**失败处理:** 记录详细错误

---

## 回归测试执行计划

### 后端测试命令
```bash
cd D:/tis_project
python -m pytest tests/ -v --tb=short 2>&1 | tail -50
```
**目标通过率:** 全部通过（或已知失败用例不影响功能）

### 前端测试命令
```bash
cd D:/tis_project/frontend
npm run test:unit 2>&1 | tail -30
# 如果无 test:unit，则跳过
```
**目标通过率:** N/A（无标准前端单元测试框架）

### 冒烟测试门禁
任何代码提交前必须满足：
- [ ] pytest tests/week2/ 通过（当前66个）
- [ ] 路径A 12步通过
- [ ] 路径B 12步通过（如果修改了approval相关代码）

---

## daily_integration_log.md 结构定义

### 模板格式
```markdown
# TIS 每日集成检查日志

## 日期
YYYY-MM-DD

## 冒烟测试路径A结果（直接执行）

| Step | 端点 | HTTP状态 | 结果 |
|------|------|----------|------|
| 1 | POST /api/projects | 200 | ✅ PASS |
| ... | ... | ... | ... |

**路径A通过步数:** X/12
**路径A断裂点:** Step N（如果存在）

## 冒烟测试路径B结果（老板审批）

| Step | 端点 | HTTP状态 | 结果 |
|------|------|----------|------|
| 6a | POST /api/v1/evaluations/{id}/approve (submit_to_boss) | 200 | ✅ PASS |
| 6b | POST /api/v1/evaluations/{id}/approve (boss approve) | 200 | ✅ PASS |
| ... | ... | ... | ... |

**路径B通过步数:** X/12
**路径B断裂点:** Step N（如果存在）

## 回归测试结果

- 总测试数: N
- 通过数: X
- 失败数: Y
- 通过率: XX%

**已知失败（Pre-existing）:** [列表]

## 今日修改文件

（如果验证任务不修改代码，此处为空）

## 新发现问题

（如果有，记录详细错误信息）

## 结论

✅ 全链路通过（路径A + 路径B）/ ❌ 在 Step N 中断
```

---

## 开发规范

### 3-Strike Error Protocol
同一错误出现3次时：
1. 停止当前开发任务
2. 在findings.md记录：错误现象、出现位置、根因假设
3. 向用户汇报，不自行盲目修复

### 冒烟测试门禁
任何代码提交前必须满足：
- [ ] pytest tests/week2/ 通过（当前66个）
- [ ] 路径A 12步通过
- [ ] 路径B 12步通过（如果修改了approval相关代码）

---

## 验证计划执行流程

1. **环境检查** - 确认 Docker 服务可用
2. **冒烟测试路径A** - 按 12 步顺序执行，任何失败立即停止
3. **冒烟测试路径B** - 按 12 步顺序执行，任何失败立即停止
4. **回归测试** - 运行完整测试套件
5. **日志创建** - 写入 daily_integration_log.md
6. **审查** - 调用 requesting-code-review 技能