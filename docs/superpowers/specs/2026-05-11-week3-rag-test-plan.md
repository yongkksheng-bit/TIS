# Week 3 RAG 生成技术方案测试计划

## 概述

**目标**：验证 TIS 系统 Week 3 RAG 生成技术方案功能，测试多章节生成与双轨 RAG 检索

**范围**：基于 Project 117（惠州交通大厦食堂配送服务），生成 3-5 个技术方案章节

**前置条件**：
- Week 1-2 E2E 测试已通过（Project 117 已创建）
- 双轨 RAG 数据已就绪（positive=6140, negative=7585）

---

## 测试数据

### 项目信息
| 字段 | 值 |
|------|-----|
| 项目 ID | 117 |
| 项目名称 | HZ_2025_Canteen_Test |
| 招标文件 | 2025_惠州交通大厦食堂管理和食材配送服务_招标文件.docx |

### 章节列表
| 序号 | 章节名称 | 说明 |
|------|----------|------|
| 1 | 第一章：冷链配送方案 | 配送能力相关 |
| 2 | 第二章：食材溯源方案 | 食材溯源相关 |
| 3 | 第三章：服务保障方案 | 服务方案相关 |

---

## 实现方案

### 核心 API

**生成单章节**
```bash
POST /api/v1/projects/{project_id}/generate-section
```

**查询章节列表**
```bash
GET /api/v1/projects/{project_id}/sections
```

### 请求参数（generate-section）

```json
{
  "section_name": "第一章：冷链配送方案",
  "generation_mode": "auto",
  "insider_notes": null,
  "top_k": 5,
  "scoring_dimension_tags": ["配送能力"],
  "region_tags": ["广东省"],
  "use_dual_track_rag": true
}
```

**参数说明**：
- `generation_mode`: `auto` — 标准生成，无需 insider_notes
- `use_dual_track_rag`: `true` — 启用双轨 RAG，注入正/负样本
- `scoring_dimension_tags`: 过滤相关评分维度 chunks
- `region_tags`: 过滤相关地区 chunks

### 预期响应（generate-section）

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "project_id": 117,
    "section_name": "第一章：冷链配送方案",
    "content": "（LLM 生成的章节内容）",
    "mode": "auto",
    "token_usage": {
      "prompt_tokens": 1200,
      "completion_tokens": 450,
      "total_tokens": 1650
    },
    "source_chunk_count": 5,
    "generation_timestamp": "2026-05-11T12:00:00Z"
  }
}
```

---

## 执行步骤

### 步骤 1：生成第一章（冷链配送方案）

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/generate-section \
  -H "Content-Type: application/json" \
  -d '{
    "section_name": "第一章：冷链配送方案",
    "generation_mode": "auto",
    "top_k": 5,
    "scoring_dimension_tags": ["配送能力"],
    "region_tags": ["广东省"],
    "use_dual_track_rag": true
  }'
```

Expected: HTTP 200, content non-empty, source_chunk_count > 0

### 步骤 2：生成第二章（食材溯源方案）

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/generate-section \
  -H "Content-Type: application/json" \
  -d '{
    "section_name": "第二章：食材溯源方案",
    "generation_mode": "auto",
    "top_k": 5,
    "scoring_dimension_tags": ["食材溯源"],
    "region_tags": ["广东省"],
    "use_dual_track_rag": true
  }'
```

### 步骤 3：生成第三章（服务保障方案）

```bash
curl -X POST http://localhost:8000/api/v1/projects/117/generate-section \
  -H "Content-Type: application/json" \
  -d '{
    "section_name": "第三章：服务保障方案",
    "generation_mode": "auto",
    "top_k": 5,
    "scoring_dimension_tags": ["服务方案"],
    "region_tags": ["广东省"],
    "use_dual_track_rag": true
  }'
```

### 步骤 4：查询章节列表

```bash
curl http://localhost:8000/api/v1/projects/117/sections
```

Expected: 3 sections returned

### 步骤 5：验证数据库

```bash
docker exec tis_db psql -U postgres -d canteen_system -c "SELECT id, project_id, section_name, LENGTH(content) as content_len FROM project_sections WHERE project_id=117;"
```

Expected: ≥3 rows, content_len > 0

---

## 验收标准

### 功能验收
- [ ] 生成 3 个章节全部返回 HTTP 200
- [ ] 每个章节 content 非空
- [ ] `use_dual_track_rag=True` 时 positive/negative chunks 均被检索
- [ ] 章节存储到 project_sections 表

### 性能验收
- [ ] 单章节生成时间 < 30s（正常负载）
- [ ] token_usage 字段有值

### 数据验收
- [ ] project_sections 表有 ≥3 条记录
- [ ] 每个 section_name 唯一

---

## 风险与备选

| 风险 | 缓解方案 |
|------|----------|
| LLM 超时（>120s）| 检查 ai_service 健康状态 |
| RAG 返回 0 chunks | 验证 win_signal 分布（已知 positive=6140）|
| 内容为空 | 检查 use_dual_track_rag 参数是否正确传递 |
| 存储失败 | 检查 project_sections 表是否存在 |

---

## 创建时间
2026-05-11