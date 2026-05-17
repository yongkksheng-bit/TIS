# ConfirmationView.vue API 前缀修复验证计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 验证 `ConfirmationView.vue` 第 207 行和第 249 行的 API 路径修复后，Week 1 → Week 2 流程可完整跑通。

**Architecture:** 前端修复通过在 `apiClient.get/post()` 路径前添加 `/api/` 前缀，与 nginx `location /api/` 路由规范对齐，使请求正确代理到 FastAPI 后端。

**Tech Stack:** FastAPI, Vue.js, pytest, Docker

---

## 前置条件

- Docker 服务运行中：`docker compose ps` 确认 `tis_backend` 和 `tis_frontend` healthy
- 项目 Project 117 存在（Week 1-6 E2E 测试已创建）
- PDF 文件：`2025_惠州交通大厦食堂管理和食材配送服务_招标文件.docx`

---

## 验证步骤

### Task 1: 重建前端镜像（包含修复）

- [ ] **Step 1: 确认修复已应用**

```bash
# 验证 ConfirmationView.vue 中两处已修复
grep -n "/api/projects" frontend/src/views/ConfirmationView.vue
# 预期输出：
# 207:    const data = await apiClient.get(`/api/projects/${projectId.value}/confirmation-data`)
# 249:    await apiClient.post(`/api/projects/${projectId.value}/confirm-parsing`, {
```

- [ ] **Step 2: 重建前端 Docker 镜像**

```bash
cd D:/tis_project
docker compose build --no-cache frontend
```

**验收标准：** `docker compose up -d frontend` 成功，JS 文件包含 `/api/projects/`

- [ ] **Step 3: 验证 Docker 内 JS 包含修复**

```bash
# 进入 frontend 容器检查编译后的 JS
docker exec tis_frontend grep -o '/api/projects/[^"'"'"']*confirmation-data' /usr/share/nginx/html/assets/*.js | head -1
```

---

### Task 2: 端到端手动验证（Week 1 → Week 2）

- [ ] **Step 4: 访问前端并登录**

浏览器打开：http://localhost:3000

- [ ] **Step 5: 上传招标文件触发解析**

1. 点击"上传招标文件"
2. 拖拽 PDF 文件到上传区
3. 点击"开始智能解析"
4. 等待解析完成（progress 100%）
5. 自动跳转到 `/projects/{id}/confirm`

**验收标准：** 页面成功加载，确认表单显示 OCR 提取的字段数据（项目名称、业主单位、预算金额等），不再出现"无法加载OCR数据"警告

- [ ] **Step 6: 确认并提交**

1. 填写/确认 `bid_open_date`（提交投标文件截止时间）
2. 点击"确认并进入评估"
3. 页面跳转到 `/projects/{id}/evaluation`

**验收标准：** `POST /api/projects/{id}/confirm-parsing` 返回 200，页面成功跳转到评估页，数据库 `projects.status = 'evaluation_ready'`

- [ ] **Step 7: 验证数据库状态**

```sql
SELECT id, project_name, status FROM projects WHERE id = 117;
-- 预期：status = 'evaluation_ready'
```

---

### Task 3: pytest 自动化验证

- [ ] **Step 8: 运行路径规范测试**

```bash
cd D:/tis_project
python -m pytest tests/frontend/test_api_path_convention.py::TestFrontendApiPathConvention::test_confirmation_view_has_api_prefix -v
```

**预期输出：** `PASSED`

- [ ] **Step 9: 运行后端相关测试确保无回归**

```bash
cd D:/tis_project
python -m pytest tests/week1/test_confirmation_service.py -v
python -m pytest tests/week1/test_api_projects.py -v
```

**预期输出：** 全部 `PASSED`

---

## 失败处理

若 Task 2 Step 5 OCR 数据仍然加载失败：
1. 检查浏览器 DevTools → Network 标签
2. 确认请求 URL 为 `/api/projects/{id}/confirmation-data`（不是 `/projects/...`）
3. 若仍为 `/projects/` 前缀，说明 Docker 镜像未更新，重复 Task 1 Step 2

若 Task 2 Step 6 提交失败：
1. 检查 Network 确认 POST 路径为 `/api/projects/{id}/confirm-parsing`
2. 查看后端日志：`docker compose logs tis_backend --tail=50`

---

## 修复文件清单

| 文件 | 变更 | 状态 |
|------|------|------|
| `frontend/src/views/ConfirmationView.vue` | Line 207, 249 添加 `/api/` 前缀 | ✅ 已修复 |
| `tests/frontend/test_api_path_convention.py` | 新增路径规范测试 | ✅ 已创建 |
| `tests/frontend/__init__.py` | Python 包初始化文件 | ✅ 已创建 |
