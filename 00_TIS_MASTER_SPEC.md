# TIS 系统最终架构与设计规范
## Tender Intelligence System - Master Architecture & Design Specification

**版本**：v1.0
**日期**：2026-03-25
**状态**：正式版（经过架构审查与逻辑完善）
**适用对象**：开发团队（Claude）、业务负责人、系统架构师

---

## 一、系统定位与商业逻辑

### 1.1 核心命题

打破"无关系不中标"的行业魔咒，通过系统化能力将无关系项目中标率提升 30%+，有关系项目废标率降至 0%。

### 1.2 双模式战略

| 维度 | 有关系项目（稳赢模式） | 无关系项目（破局模式） |
|------|----------------------|----------------------|
| **策略核心** | 确保 100% 不废标，标准响应 | 极致优化，技术标拿满商务分，价格博弈 |
| **技术标生成** | 专员录入要点 → AI 定制化生成 | AI 全自动（RAG 最大化召回） |
| **报价策略** | 正常利润（成本+8-15%） | 激进低价（成本+2%）赌技术分优势 |
| **审批流** | 快速通过 | 系统建议 abandon 时可强制 worthy |

### 1.3 数据飞轮

11份历史文件（冷启动）→ 系统使用后积累数据 → 知识库进化 → AI模型训练（Week 8）→ 更准中标率 → 更多数据

---

## 二、系统架构总览

### 2.1 技术栈

- **后端**：Python 3.11 + FastAPI
- **数据库**：PostgreSQL + pgvector（向量检索）
- **AI/ML**：PaddleOCR（文档识别）、DeepSeek API（文本生成）、XGBoost（Week 8 定价模型）
- **存储**：MinIO（对象存储）、Redis（缓存）
- **前端**：Vue 3 + Element Plus（管理端）、微信小程序（Week 8）

### 2.2 八阶段闭环流程

| Week | 阶段 | 核心能力 |
|------|------|---------|
| 1 | 感知层 | PDF/Word 上传、扫描件 OCR、结构化提取、并排确认 |
| 2 | 决策层 | 资质精确匹配、时间充裕度计算、业主画像、审批流 |
| 3 | 生成层 | RAG 检索、双模式生成、人机协同编辑器、评分点索引 |
| 4 | 定价层 | 成本录入、博弈矩阵、版本控制、定价决策 |
| 5 | 风控层 | 自动审查、PDF高亮标注、强制拦截、Word封装输出 |
| 6 | 进化层 | 中标DNA提取、废标陷阱入库、废弃草稿复活、知识库自清理 |
| 7 | 管理层 | 多项目并行冲突检测、日历视图、老板驾驶舱、封装打印优化 |
| 8 | 自动驾驶层 | 竞争对手爬虫监控、ML定价模型、移动端小程序、RAG Chatbot |

---

## 三、核心业务规则（全局约束）

### R1. 精确匹配原则（生死线）

证书名称必须精确匹配标准库编码，禁止模糊匹配。

- `"食品经营许可证"` vs `"食品生产许可证"` 必须区分（exclude_keywords 互斥）
- `"一级资质"` vs `"二级资质"` 必须区分（等级关键词精确匹配）

### R2. 审批权限

- 专员拥有独立初筛审批权（worthy/unworthy），点击立即生效
- 老板拥有事后监督权，可随时推翻（terminate/revive），硬终止或复活
- 推翻操作必须填写理由，记录审计日志

### R3. 强制拦截机制

- 形式审查存在 `risk_level='fatal'` 且未处理时，禁止生成最终标书
- 资质有效期 < 开标日期时，中标概率强制归零，专员标记 worthy 需填写覆盖理由
- 报价 > 预算限价时，强制二次确认

### R4. 知识库进化

- 中标项目技术标段落 quality_score +20，优先参与 RAG 检索
- `usage_count=0` 且 3 个月未使用的知识块标记 deprecated
- 废标原因自动提取，更新形式审查清单模板

---

## 四、项目全生命周期状态机

### 4.1 状态定义

```
uploaded → parsing → parsed → evaluating → evaluation_ready
    │         │          │           │              │
    │         │          │           │              ▼
    │         │          │           │      ┌──────────────┐
    │         │          │           │      │ specialist   │─── worthy ───┐
    │         │          │           │      │ decide       │              │
    │         │          │           │      └──────────────┘              │
    │         │          │           │              │                      │
    │         │          │           │              ▼                      │
    │         │          │           │      unworthy ───┐                 │
    │         │          │           │                 │                 │
    │         │          │           │                 ▼                 │
    │         │          │           │      discarded (放弃库)            │
    │         │          │           │                 │                 │
    │         │          │           └─────────────────┴─────────────────┘
    │         │          │                             │
    │         │          └─────────────────────────────┘
    │         │                        │
    │         ▼                        ▼
    │   parsing_failed              generating_documents (Week 3)
    │   (retry/cancel)                    │
    │                                     ▼
    │                         awaiting_pricing (Week 4)
    │                                     │
    │                                     ▼
    │                         awaiting_review (Week 5)
    │                                     │
    │                                     ▼
    │                         completed → bid_outcome (Week 6)
    │                                     │
    └─────────────────────────────────────┘
```

### 4.2 终止与复活路径

- **终止**：`terminated_by_boss`（老板推翻），状态变为 `terminated_by_boss`
- **复活**：`revived`（老板复活），从 `discarded_projects` 恢复

---

## 五、双模式状态机的动态切换与强制回滚机制

### 5.1 动态模式切换原则

双模式（有内幕/无内幕）的区分不是在项目创建时锁定，而是根据业务实际情况动态调整。

**核心原则**：允许随时切换，但切换模式等同于"清空当前阶段进度并回滚重做"，以保证底层数据的绝对干净和闭环。

### 5.2 模式切换触发点

- **初始锚定**：Week 2 初筛审批时确定初始 `relationship_flag` 和对应的生成模式
- **中途切换**：Week 3（技术标生成）和 Week 4（定价）阶段，提供全局【更改关系状态】按钮（仅限老板权限操作）

### 5.3 强制回滚逻辑

#### 无关系 → 有关系（升维）

当 `relationship_flag` 从 `false` 变为 `true` 时：

1. **技术标处理**：
   - 将当前全自动生成的技术标版本标记为 `archived_due_to_mode_switch`
   - 强制回退到 Week 3 的开头
   - 强制要求标书专员人工补录"技术要点"（标签式 + 自然语言）
   - 基于内幕要求重新生成定制化标书

2. **定价处理**：
   - 清空之前的所有定价策略数据
   - 强制切换为"稳赢利润模型"（成本+8-15%）
   - 重新执行定价流程

3. **状态记录**：
   - 记录切换原因和切换前后的版本快照
   - 记录操作人和操作时间

#### 有关系 → 无关系（降维，关系破裂）

当 `relationship_flag` 从 `true` 变为 `false` 时：

1. **技术标处理**：
   - 废弃已生成的定制化标书，标记为 `discarded_due_to_mode_switch`
   - 系统接管进入全自动 RAG 极致优化模式
   - 重新执行 Week 3 技术标生成流程

2. **定价处理**：
   - 废弃已生成的定价策略
   - 强制切换为"低价博弈"策略（成本+2%）
   - 重新执行定价流程

3. **状态记录**：
   - 记录切换原因（包括关系破裂的具体说明）
   - 记录操作人和操作时间

### 5.4 数据隔离保障

- 每次模式切换前，系统自动生成完整的数据快照
- 切换过程中的所有操作均记录审计日志
- 废弃的技术标和定价数据不物理删除，标记为 `archived` 状态供回溯分析

---

## 六、数据分层架构（单一事实来源原则）

### 6.1 数据分层职责划分

#### 第一层：事实确认层（Week 1）

**核心职责**：标书专员在并排界面的核心动作是确认"客观事实"

- OCR 有没有错别字？
- 日期有没有提取错误？
- 证书是否正确映射到 `standard_cert_id`？

**数据标准**：
- 一旦数据被标记为 `is_validated=true`，它就成为不可篡改的单一事实来源（Single Source of Truth）
- 专员在 Week 1 修改的任何字段（如证书有效截止日期），Week 2 必须直接读取该人工修正值

**禁止事项**：
- Week 1 不得进行任何业务评估判断（如"这个证书能不能用"）
- Week 1 不得做资格有效性的最终判定

#### 第二层：业务评估层（Week 2 及之后）

**核心职责**：拿着 Week 1 已确认的"事实清单"去做业务评估

**Week 2 评估引擎职责**：
- 拿着 Week 1 确认的事实清单（我们有什么证书、哪天过期）
- 对比招标文件的业务要求（需要什么证书、开标日是哪天）
- 做交集比对与逻辑运算

**Week 2 禁止事项**：
- 绝对禁止重新解析或重新做模糊匹配
- 禁止对 Week 1 已确认的事实进行二次验证（除非发现明显的录入错误）
- 禁止在 Week 2 阶段尝试重新 OCR 或补充识别遗漏的证书

### 6.2 数据交接标准

1. **日期交接**：如果 Week 1 专员修正了证书的有效截止日期，Week 2 必须直接读取这个人工修正后的日期来判断是否覆盖开标日

2. **缺失判定**：如果 Week 1 漏了某个招标文件要求的证书（如没上传或没识别出来），Week 2 直接判定为"缺失 (missing)"，在初筛报告里标红警告，**不在 Week 2 尝试重新跑 OCR 找证书**

3. **回溯修正**：如果专员在 Week 2 发现"缺失"是因为自己 Week 1 漏确认了，不能在 Week 2 直接改，必须点击【回退到解析阶段】，在 Week 1 的数据表里改完，再重新生成 Week 2 的报告

### 6.3 各层级数据信任边界

| 数据来源 | Week 1 信任度 | Week 2 信任度 | Week 3+ 信任度 |
|---------|---------------|---------------|---------------|
| `ocr_extractions.is_validated=true` | - | ✅ 单一事实来源 | ✅ 单一事实来源 |
| `ocr_extractions.is_validated=false` | 待确认 | ❌ 不可用 | ❌ 不可用 |
| `standard_cert_id IS NOT NULL` | 关联建议 | ✅ 精确匹配结果 | ✅ 精确匹配结果 |
| `tender_documents.extracted_data` | AI解析初稿 | ✅ 业务事实 | ✅ 业务事实 |

---

## 七、数据库设计（核心实体）

### 7.1 核心实体关系

```
projects (1)
  ├─ tender_documents (1:1) 招标文件解析
  ├─ bid_documents (1:N) 投标文件
  │    └─ document_images (1:N) 提取的图片
  │         └─ ocr_extractions (1:N) OCR识别结果 [单一事实来源]
  ├─ bid_evaluation_reports (1:N) 初筛报告
  ├─ tech_proposal_tasks (1:N) 技术标生成任务
  ├─ pricing_decisions (1:N) 定价决策
  ├─ formal_review_items (1:N) 形式审查检查项
  ├─ bid_outcomes (1:1) 投标结果
  └─ approval_logs (1:N) 审批审计日志
```

### 7.2 核心表清单

| 表名 | 所属层 | 核心用途 |
|------|-------|---------|
| `projects` | 全局 | 项目主表（状态机、关系标记） |
| `users` | 全局 | 用户表（专员/老板/财务，RBAC） |
| `tender_documents` | Week 1 | 招标文件解析结果 |
| `bid_documents` | Week 1 | 投标文件元数据 |
| `document_images` | Week 1 | PDF提取的图片 |
| `ocr_extractions` | Week 1 | OCR结构化数据 [单一事实来源] |
| `standard_certifications` | Week 1 | 标准资质库（精确匹配规则） |
| `owner_profiles` | Week 2 | 业主画像库 |
| `bid_evaluation_reports` | Week 2 | 初筛报告 |
| `approval_logs` | Week 2 | 审批审计日志 |
| `discarded_projects` | Week 2 | 废弃项目库 |
| `knowledge_chunks` | Week 3 | 知识库分块（向量） |
| `tech_proposal_tasks` | Week 3 | 技术标生成任务 |
| `scoring_indexes` | Week 3 | 评分点索引 |
| `cost_estimates` | Week 4 | 成本测算（版本控制） |
| `pricing_decisions` | Week 4 | 定价决策 |
| `price_history` | Week 4 | 价格历史库 |
| `formal_review_items` | Week 5 | 形式审查检查项 |
| `abandoned_drafts` | Week 5 | 废弃草稿库 |
| `final_bid_documents` | Week 5 | 最终标书 |
| `bid_outcomes` | Week 6 | 投标结果 |
| `winning_dna` | Week 6 | 中标DNA提取 |
| `disqualification_traps` | Week 6 | 废标陷阱库 |
| `draft_revivals` | Week 6 | 草稿复活记录 |
| `project_schedules` | Week 7 | 多项目资源调度 |
| `dashboard_metrics` | Week 7 | 数据看板指标 |
| `competitor_monitoring` | Week 8 | 竞争对手监控 |
| `pricing_ml_models` | Week 8 | AI定价模型 |
| `ai_chat_sessions` | Week 8 | 智能问答会话 |

---

## 八、关键算法逻辑

### 8.1 精确资质匹配算法

```python
def exact_match(ocr_text: str, standard_cert: dict) -> bool:
    cleaned = normalize(ocr_text)  # 去空格、统一中文数字

    # 1. 必须包含所有 required_keywords
    for kw in standard_cert.required_keywords:
        if kw not in cleaned:
            return False

    # 2. 必须不包含任何 exclude_keywords
    for kw in standard_cert.exclude_keywords:
        if kw in cleaned:
            return False

    # 3. 等级精确匹配（一级 ≠ 二级）
    if '一级' in standard_cert.full_name and '一级' not in cleaned:
        return False

    # 4. 编号正则验证（如有）
    if ocr_cert_number and standard_cert.pattern:
        if not re.match(standard_cert.pattern, ocr_cert_number):
            return False

    return True
```

### 8.2 综合中标概率计算（Week 2 启发式）

```python
def calculate_win_probability(qual_score, time_level, relationship_index, competition_count):
    # 权重：资质 40% + 时间 20% + 关系 30% + 竞争 10%
    time_score = {'expired': 0, 'urgent': 40, 'tight': 60, 'normal': 80, 'relaxed': 100}[time_level]

    base_prob = (
        qual_score * 0.4 +
        time_score * 0.2 +
        relationship_index * 0.3 +
        max(0, 100 - competition_count * 10) * 0.1
    ) / 100

    # 致命风险归零
    if qual_score < 60 or time_level == 'expired':
        base_prob = 0

    return base_prob
```

### 8.3 RAG 检索算法（Week 3）

```python
def hybrid_retrieval(query_vector, project_context, top_k=5):
    sql = """
    SELECT *, content_vector <=> query_vector as distance,
           (quality_score / 100.0 * 0.3 + usage_count / 100.0 * 0.1) as weight_boost
    FROM knowledge_chunks
    WHERE is_deprecated = FALSE
      AND metadata->>'owner_type' = %s
    ORDER BY (distance * 0.6 - weight_boost) ASC
    LIMIT %s
    """
    # 阈值过滤：distance < 0.3（cosine > 0.7）
    return [r for r in results if r.distance < 0.3]
```

### 8.4 定价期望收益最大化（Week 4）

```python
def search_optimal_price(cost, budget, win_prob_func):
    best_expectation = 0
    optimal_price = cost * 1.05

    for markup in [0.02, 0.03, 0.05, 0.08, 0.10, 0.12, 0.15]:
        price = cost * (1 + markup)
        if price > budget * 0.95:
            continue

        prob = win_prob_func(price)
        profit = price - cost
        expectation = profit * prob

        if expectation > best_expectation:
            best_expectation = expectation
            optimal_price = price

    return optimal_price, best_expectation
```

---

## 九、用户角色与权限矩阵（RBAC）

| 功能模块 | 标书专员 | 老板 | 财务 |
|---------|---------|------|------|
| 项目创建/上传 | ✅ | ✅ | ❌ |
| 文件解析确认 | ✅ | ✅（查看） | ❌ |
| 初筛报告查看 | ✅ | ✅ | ✅ |
| 初筛审批（worthy/unworthy） | ✅ 独立审批 | ✅ 事后推翻 | ❌ |
| 内幕/无内幕标记 | ✅ | ✅ | ❌ |
| 技术标编辑 | ✅ 主导 | ✅ 查看+批注 | ❌ |
| AI 生成触发 | ✅ | ❌ | ❌ |
| 成本录入 | ✅ | ✅ | ✅ |
| 定价决策（最终） | ❌ | ✅ 决策权 | ✅ 建议权 |
| 形式审查确认 | ✅ 执行 | ✅ 查看 | ❌ |
| 最终标书下载 | ✅ | ✅ | ❌ |
| 复盘结果录入 | ✅ | ✅ | ❌ |
| 数据看板 | ✅ 项目级 | ✅ 公司级 | ✅ 财务级 |
| 系统管理 | ❌ | ✅ | ❌ |
| AI 模型训练触发 | ❌ | ✅ | ❌ |
| 关系模式切换 | ❌ | ✅ | ❌ |

---

## 十、非功能性需求

### 10.1 性能指标

- **并发**：支持 3 个标书专员同时操作
- **响应时间**：文件解析 < 30 秒（50MB PDF），RAG 检索 < 2 秒，页面加载 < 3 秒
- **存储**：MinIO 对象存储，支持 1TB 标书文件历史归档

### 10.2 安全与合规

- **数据隔离**：项目级权限隔离
- **审计**：所有审批操作记录不可篡改日志
- **备份**：每日自动备份 PostgreSQL，保留 30 天
- **脱敏**：敏感资质信息展示时脱敏

### 10.3 部署与运维

- **容器化**：Docker Compose 一键启动
- **监控**：Health check 接口 /health

---

## 十一、实施路线图

### Phase 1: MVP（Week 1-6）- 核心闭环

目标：实现从文件上传到复盘的全流程跑通

### Phase 2: 优化（Week 7）- 规模化

目标：支持多项目并行，数据看板辅助决策

### Phase 3: 智能化（Week 8）- 自动化

目标：减少人工操作 50%，实现数据驱动的投标策略

---

## 十二、给开发团队的最终指令

1. **严格遵循数据库设计**：外键关系、JSONB 字段结构、CHECK 约束必须一致
2. **Week 1 是基础**：PaddleOCR 部署和精确匹配算法必须 100% 可靠
3. **选项 A 审批流**：务必实现"专员审批立即生效 + 老板事后推翻"的状态机
4. **Prompt 工程**：Week 3 的 ABCD 策略必须体现在 DeepSeek 的 system prompt 中
5. **渐进式交付**：每完成一个 Week，必须能通过该周的验收 checklist 才能进入下一周
6. **单一事实来源**：Week 1 确认的数据是 Week 2+ 的唯一数据来源，禁止跨层重新解析
7. **动态模式切换**：双模式可随时切换，切换必须触发完整的强制回滚流程

---

**文档控制**：
- 主版本：v1.0（2026-03-25）
- 本文档经过全面的架构审查与逻辑完善，涵盖双模式动态切换机制和单一事实来源数据分层设计
- 后续迭代基于实际开发反馈进行调整，但总体框架不变
