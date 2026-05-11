# Week 1-2 端到端流程测试计划

## 概述

**目标**：解锁 TIS 系统完整流程测试，验证 projects 表从 0 条到有数据的流转

**范围**：Week 1-2 核心流程
1. 创建项目 → 2. 上传招标文件 → 3. 初筛评估（RAG）

**数据来源**：现有的 6 个历史招标文件

---

## 测试数据

### 招标文件清单

| 文件名 | 大小 | 所属项目 |
|--------|------|----------|
| `2025_惠州交通大厦食堂管理和食材配送服务_招标文件.docx` | 83KB | 惠州交通局 |
| `2025_某部2026年副食品配送服务采购项目（第二次）_子包3_招标文件.docx` | 252KB | 某部子包3 |
| `2025_广东省粤北片区监狱（乐昌、韶关、武江、北江）2025-2026年度罪犯大宗生活物资（大米及食用油）采购项目_招标文件.docx` | 77KB | 粤北片区 |
| `2025_广东省肇庆片区（肇庆、四会、会城监狱）2025-2026年度服刑人员大宗生活物资（大米及食用油）采购项目_招标文件.docx` | 72KB | 肇庆片区 |
| `2025_监所羁押人员食堂食材配送服务采购项目_招标文件.docx` | 63KB | 监所羁押 |
| `2025_2026-2027年流浪乞讨人员伙房购买配送食材服务项目_采购包 1_招标文件.docx` | 101KB | 流浪乞讨 |

路径：`data/historical_documents/tenders/`

---

## 实现方案

### 方案 B：快速解锁（立即执行）

**步骤 1：创建测试项目**
```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "2025_惠州交通大厦食堂管理和食材配送服务",
    "agency_project_code": "HZJJ-2025001",
    "plan_code": "441301-2025-00001",
    "owner_unit": "惠州市交通运输局",
    "province": "广东",
    "region": "惠州"
  }'
```

**步骤 2：上传招标文件**
```bash
curl -X POST http://localhost:8000/api/v1/projects/{id}/upload-tender \
  -F "file=@data/historical_documents/tenders/2025_惠州交通大厦..._招标文件.docx"
```

**步骤 3：触发初筛评估**
```bash
curl -X POST http://localhost:8000/api/v1/projects/{id}/evaluations/generate
```

**步骤 4：验证结果**
- 检查 projects 表有新记录
- 检查 RAG 评估返回结果
- 检查 tender_documents 表有记录

---

### 方案 C：E2E 测试（可选）

**目标**：编写 Playwright 自动化测试脚本

**输出文件**：`tests/e2e/test_week1_week2_flow.py`

**测试用例**：
1. `test_create_project` - 创建项目
2. `test_upload_tender_document` - 上传招标文件
3. `test_generate_evaluation` - 触发初筛评估
4. `test_full_flow` - 完整流程串联

---

## 验收标准

### B 方案（快速解锁）
- [ ] projects 表有 ≥1 条记录
- [ ] tender_documents 表有 ≥1 条记录
- [ ] 初筛评估 API 返回 200

### C 方案（E2E 测试）
- [ ] Playwright 测试脚本可运行
- [ ] 3 个测试用例全部通过
- [ ] 测试结果保存到测试报告

---

## 风险与备选

| 风险 | 缓解方案 |
|------|----------|
| API 端点不存在 | 先检查端点定义 |
| 文件上传失败 | 检查 MinIO 服务 |
| RAG 评估超时 | 检查 ai_service 健康状态 |

---

## 后续扩展

Week 1-2 测试通过后，可继续：
- Week 3: RAG 生成技术方案
- Week 4: 定价博弈验证
- Week 5: 形式审查验证

---

## 创建时间
2026-05-11
