投标智能辅助系统（TIS）总体产品需求文档（PRD）
版本：v1.0
日期：2026-03-24
适用对象：开发团队（Claude）、业务负责人、系统架构师
一、项目概述
1.1 产品定位
投标智能辅助系统（Tender Intelligence System, TIS） 是专为食材配送与物业服务企业设计的智能投标决策与标书生成平台。
核心价值主张：
有关系项目：通过系统化响应确保 100% 中标（不漏分、不废标）
无关系项目：通过极致技术标优化 + 精准博弈定价，最大化中标概率，打破"无关系不中标"的行业魔咒
1.2 业务背景
当前痛点：投标行业水很深，无内幕关系很难中标；标书制作耗时（3-7天/份）；资质管理混乱（扫描件易过期）
数据基础：初期基于 11 份历史投标文件（5 中标 + 6 未中标）冷启动，后续持续自进化
技术栈：PostgreSQL + pgvector、PaddleOCR、DeepSeek API、FastAPI、Vue3、Docker
1.3 成功指标
短期（3个月）：无关系项目中标率提升 30%，有关系项目废标率降至 0%
中期（6个月）：标书制作时间缩短 50%（从 5 天到 2.5 天）
长期（12个月）：积累 100+ 项目数据，AI 定价模型准确率达到 80%+
二、系统架构总览
2.1 整体业务闭环
[Week 1] 文件智能解析          [Week 2] 初筛决策           [Week 3] 标书生成
├─ PDF/Word 上传              ├─ 资质精确匹配             ├─ RAG 检索知识库
├─ 扫描件 OCR (PaddleOCR)     ├─ 时间充裕度计算           ├─ LLM 生成技术方案
├─ 并排确认界面               ├─ 业主画像匹配             ├─ 人机协同编辑器
└─ 结构化数据入库             ├─ 选项A审批流              └─ 评分点索引生成
                              └─ 智能评估报告             └─ 业绩案例关联

[Week 4] 博弈定价决策         [Week 5] 形式审查与输出      [Week 6] 复盘与进化
├─ 成本录入（三角色）          ├─ 自动审查 vs 招标文件      ├─ 中标 DNA 提取
├─ 概率-利润矩阵              ├─ PDF 高亮标注风险点        ├─ 废标陷阱入库
├─ 定价版本控制               ├─ 强制拦截生成              ├─ 废弃草稿复活
└─ AI 模型冷启动/训练          ├─ Word 标书生成            └─ 知识库自清理
                              └─ 封装指南打印

[Week 7] 多项目协同           [Week 8] 智能化进阶
├─ 资源冲突检测               ├─ 竞争对手自动驾驶舱
├─ 日历与优先级               ├─ ML 定价模型训练
├─ 数据看板（老板驾驶舱）       ├─ 移动端小程序
└─ 封装打印优化               └─ RAG Chatbot 知识问答
2.2 技术架构图
┌──────────────────────────────────────────────────────────────┐
│                        用户层                               │
│   标书专员（执行+审批）   老板（监督+推翻）   财务（成本+建议）  │
└──────────────────┬─────────────────────────────┬───────────┘
                   │                             │
┌──────────────────▼─────────────┐  ┌───────────▼────────────┐
│       应用层 (FastAPI)          │  │      前端 (Vue3)        │
│  ┌──────────────────────────┐  │  │  ┌──────────────────┐ │
│  │ Week 1: Document Parser │  │  │  │ Week 3: Editor   │ │
│  │ Week 2: Evaluation Svc  │  │  │  │ Week 4: Pricing  │ │
│  │ Week 3: Generation Svc  │  │  │  │ Week 5: Review   │ │
│  │ Week 4: Pricing Engine  │  │  │  │ Week 7: Dashboard│ │
│  │ Week 5: Formal Review   │  │  │  └──────────────────┘ │
│  └──────────────────────────┘  │  └──────────────────────┘
└──────────┬────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────┐
│                      AI/ML 层                               │
│  PaddleOCR (文档识别)    DeepSeek LLM (生成/解析)            │
│  pgvector (向量检索)     XGBoost (Week 8 定价模型)           │
└──────────┬────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────┐
│                      数据层                                 │
│  PostgreSQL (业务数据)      Redis (缓存)      MinIO (文件)    │
│  ├─ projects               ├─ session      ├─ PDF/Word    │
│  ├─ standard_certs         └─ queue         ├─ Images      │
│  ├─ knowledge_chunks (pgvector)               └─ Output     │
│  └─ bid_outcomes                                            │
└─────────────────────────────────────────────────────────────┘
三、核心业务逻辑（全流程详解）
3.1 项目全生命周期状态机
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

3.2 双模式业务逻辑（有内幕 vs 无内幕）
| 维度        | 无内幕项目（破局模式）                               | 有内幕项目（稳赢模式）                     |
| --------- | ----------------------------------------- | ------------------------------- |
| **初筛策略**  | 极致优化，技术标拿满商务分                             | 标准响应，确保不废标即可                    |
| **技术标生成** | AI 全自动（RAG top\_k=5）<br>差异化超越（24h→12h+2h） | 专员录入要点引导<br>RAG top\_k=3，贴合业主要求 |
| **报价策略**  | 激进低价（成本+2%）赌技术分优势                         | 正常利润（成本+8-15%）                  |
| **形式审查**  | 强制严格（100%检查）                              | 同样严格（关系不能救废标）                   |
| **审批流**   | 专员审批→系统推荐 abandon 时可强制 worthy             | 专员审批→快速通过                       |

3.3 关键业务规则（全局约束）
R1. 精确匹配原则（生死线）
证书名称必须精确匹配标准库编码，禁止模糊匹配
"食品经营许可证" vs "食品生产许可证" 必须区分（exclude_keywords 互斥）
"一级资质" vs "二级资质" 必须区分（等级关键词精确匹配）
R2. 审批权限（选项 A 模式）
专员拥有独立初筛审批权（worthy/unworthy），点击立即生效
老板拥有事后监督权，可随时推翻（terminate/revive），硬终止或复活
推翻操作必须填写理由，记录审计日志
R3. 强制拦截机制
形式审查存在 risk_level='fatal' 且未处理时，禁止生成最终标书（按钮灰色）
资质有效期 < 开标日期时，中标概率强制归零，专员标记 worthy 需填写覆盖理由
报价 > 预算限价时，强制二次确认
R4. 知识库进化
中标项目技术标段落 quality_score +20，优先参与 RAG 检索
usage_count=0 且 3 个月未使用的知识块标记 deprecated
废标原因自动提取，更新形式审查清单模板
四、数据库设计（完整 ER 关系）
4.1 核心实体关系图
projects (1)
  ├─ tender_documents (1:1) 招标文件解析
  ├─ bid_documents (1:N) 投标文件（资质/技术/商务）
  │    └─ document_images (1:N) 提取的图片
  │         └─ ocr_extractions (1:N) OCR识别结果
  ├─ bid_evaluation_reports (1:N) 初筛报告（版本控制）
  ├─ tech_proposal_tasks (1:N) 技术标生成任务
  ├─ pricing_decisions (1:N) 定价决策（版本控制）
  ├─ formal_review_items (1:N) 形式审查检查项
  ├─ bid_outcomes (1:1) 投标结果（复盘）
  └─ approval_logs (1:N) 审批审计日志

owner_profiles (N) ───┐
                      ├── 关系指数计算
standard_certs (N) ───┘
                      ├── 资质匹配

knowledge_chunks (N) ───┐
                        ├── RAG检索
document_images (N) ────┘

4.2 关键表结构汇总（Week 1-8 整合）
基础层：
projects: 项目主表（状态机、关系标记）
users: 用户表（专员/老板/财务，RBAC）
owner_profiles: 业主画像库（历史合作、关系指数）
文档层：
tender_documents: 招标文件解析结果（JSON结构化）
bid_documents: 投标文件元数据
document_images: PDF提取的图片（OCR状态追踪）
ocr_extractions: OCR结构化数据（字段级，含坐标）
知识层：
standard_certifications: 标准资质库（精确匹配规则、关键词、正则）
knowledge_chunks: 知识库分块（向量 1536 维，metadata JSONB）
performance_cases: 业绩案例库（文字描述+扫描件路径）
业务层：
bid_evaluation_reports: 初筛报告（资质匹配度、时间分析、概率计算）
tech_proposal_tasks: 技术标生成任务（RAG结果、编辑版本、确认状态）
scoring_indexes: 评分点索引表（专家友好导航）
决策层：
pricing_decisions: 定价决策（成本基线、三级价格、差异原因）
formal_review_items: 形式审查检查项（系统生成+人工补充，PDF坐标高亮）
复盘层：
bid_outcomes: 投标结果（中标/未中标/废标，根因分析）
winning_dna: 中标 DNA 提取（高分段落标记）
disqualification_traps: 废标陷阱库（自动更新检查清单）
discarded_projects: 废弃项目库（支持复活）
系统层：
approval_logs: 审批审计日志（选项 A 模式全记录）
automation_tasks: 自动化任务（爬虫、模型训练定时）
dashboard_metrics: 数据看板指标（预计算）
五、功能模块详细设计（Week 1-8 整合）
5.1 Week 1: 文档智能解析引擎 (DIE)
核心功能：
多格式支持：PDF（含扫描件）/ Word 上传，MD5 去重
图像提取：PyMuPDF 提取内嵌图片，分类（营业执照/资质/合同/身份证）
OCR 识别：PaddleOCR 本地部署，中文优化，方向分类
结构化提取：
营业执照：统一信用代码（18位正则）、经营范围、有效期
资质证书：证书名称（标准化清洗）、编号、颁发机构、有效期、等级（一级/二级）
合同页：金额、甲方、日期
并排确认界面：左（PDF原图）-中（缩略图导航）-右（结构化表单，低置信度标红）
精确匹配预览：对比 standard_certifications，显示疑似证书类型建议
关键技术点：
日期标准化：2025年3月 → 2025-03-01
等级关键词统一：壹→一，防止 OCR 错误导致匹配失败
坐标记录：bbox_coords 存储，供 Week 5 PDF 高亮使用
5.2 Week 2: 初筛决策引擎 (SIE)
核心功能：
精确资质匹配引擎：
必须包含 keywords 检查（一个都不能少）
必须排除 excludes 检查（有一个就失败）
等级精确匹配（一级≠二级）
有效期覆盖检查（资质有效期 ≥ 开标日期）
时间充裕度计算：剩余天数分级（expired/urgent/tight/normal/relaxed）
业主画像匹配：历史合作次数 → 关系指数（0=无，>0=有）
成本估算：历史相似项目平均 × 通胀，或预算×75%（冷启动）
综合概率计算：启发式算法（资质40% + 时间20% + 关系30% + 其他10%）
选项 A 审批流：
专员独立审批（worthy/unworthy），立即生效
老板监督台（事后查看，可推翻 terminate/revive）
审计日志全记录
界面设计：
初筛报告页：资质匹配度环形图、时间充裕度标签、风险雷达图（致命/警告）
老板监督台：今日已审批列表、放弃库（可复活）、推翻操作按钮
5.3 Week 3: 智能标书生成引擎 (IGE)
核心功能：
双模式 RAG 检索：
无内幕：top_k=5，最大化召回，策略 ABCD（差异化超越）
有内幕：top_k=3，精准匹配专员录入要点（标签+自然语言）
Prompt 工程策略：
A. 差异化超越：标准 24h → 承诺 12h+2h 应急
B. 证据链完整：数据+流程图+案例引用
C. 专家友好：【评分点响应】标记，加粗表格
D. 业主语境：学校（守护师生健康）vs 政府（规范严谨）
人机协同编辑器：
类 Notion 富文本编辑器，段落级操作
AI 续写/改写/扩写（选中段落触发）
业绩案例拖拽插入（自动关联匹配案例）
版本历史对比（AI 生成 vs 人工修改）
评分点索引生成：自动对应章节页码，专家快速定位
数据结构：
generated_content: JSON 数组（章节标题+内容+来源引用+案例关联）
scoring_indexes: 评分项与章节页码映射表
5.4 Week 4: 博弈定价决策系统 (IPDS)
核心功能：
成本录入：三角色可录（专员/老板/财务），版本控制（v1, v2...），记录修改理由
定价策略矩阵：
激进（成本+2%）：高概率低利润
平衡（成本+8%）：中等概率中等利润
保守（成本+15%）：低概率高利润
最优：期望收益 = 利润 × 概率，最大化
概率计算：
冷启动（<20 项目）：Week 2 启发式算法
Week 8 ML 模型：XGBoost，特征（预算、关系指数、竞争烈度）
版本控制：记录三级价格（系统建议/财务建议/老板决策），差异 >5% 强制填写原因
限价拦截：报价 > 预算价时红色警告，超限时禁止提交
界面设计：
定价驾驶舱：成本基线面板、三种策略对比表格、博弈曲线图、历史对标数据
5.5 Week 5: 形式审查与输出系统 (FRCS)
核心功能：
自动审查引擎：
对比招标文件 vs 投标文件（OCR 结果）
检查项：资质有效性（过期？）、签字盖章完整性、密封要求、报价合规
双视图展示：
列表视图：检查项清单（通过/警告/致命）
PDF 高亮视图：在原始 PDF 上红框/黄框标注风险位置（使用 Week 1 坐标）
人机协同确认：
确认通过：认可系统判断
修正：系统误判时人工纠正（记录到审计）
删除：系统误报时删除（记录原因优化算法）
全局补充：新增系统未识别风险
强制拦截：存在未处理致命风险时，生成最终标书按钮灰色禁用
输出生成：
Word 合并：技术标（Week 3）+ 商务标报价（Week 4）
评分点索引页（封面后第 2 页）
封装指南：密封标签打印页、封装清单（带二维码手机核对）
5.6 Week 6: 复盘与知识进化系统 (RKE)
核心功能：
结果录入：中标/未中标/废标，中标价、竞争对手、废标原因
自动复盘：
废标：对比 Week 5 审查记录，定位失败点（形式审查？资质？）
未中标：价格分析（我们的折扣 vs 中标价）、技术标质量推断
中标：提取中标 DNA（高分段落标记，quality_score +20）
知识库进化：
热门知识加权（中标贡献）
冷门知识清理（usage_count=0 且 3 个月未用）
废标陷阱库更新（出现 2 次以上自动新增检查项模板）
废弃草稿复活：检测到项目重招（名称相似+业主相同+时间近）→ 自动提醒历史原因 → 一键复活技术标段落
5.7 Week 7: 多项目协同与数据看板 (Orchestration)
核心功能：
资源冲突检测：专员同时负责 >3 项目时警告，时间冲突检测（开标日重叠）
日历视图：老板看全公司，专员看自己，财务看待定价
老板驾驶舱 KPI：
中标率趋势（总体/有内幕/无内幕）
财务漏斗（投标额 vs 中标额 vs 成本）
风险预警（中标概率 <30% 但未放弃的项目）
封装优化：打印设置（正本/副本、双面/单面）、密封标签生成、二维码核对清单
5.8 Week 8: 智能化进阶 (Advanced AI)
核心功能：
竞争对手自动驾驶舱：
每日爬取政府采购网中标公告
监控特定对手（如 XX 餐饮）的投标频率、胜率、报价下浮率趋势
预警：对手报名参加你跟踪的项目时立即推送
ML 定价模型：
基于 20+ 项目数据训练 XGBoost
特征：预算、地区、类型、关系指数、竞争烈度
可解释性输出（特征重要性：关系 30%、预算 25%...）
移动端小程序：
手机拍照上传招标文件（OCR 自动创建草稿）
语音录入定价决策（ASR 转文字保存）
开标前 2 小时提醒 + 封装清单扫码核对
RAG Chatbot：知识问答（"ISO22000 vs HACCP 区别？"），引用历史案例回答

六、用户角色与权限矩阵（RBAC）
| 功能模块                      | 标书专员（执行者）  | 老板（决策/监督）  | 财务（成本/建议） |
| ------------------------- | ---------- | ---------- | --------- |
| **项目创建/上传**               | ✅          | ✅          | ❌         |
| **文件解析确认**                | ✅          | ✅（查看）      | ❌         |
| **初筛报告查看**                | ✅          | ✅          | ✅         |
| **初筛审批（worthy/unworthy）** | ✅ **独立审批** | ✅ **事后推翻** | ❌         |
| **内幕/无内幕标记**              | ✅          | ✅          | ❌         |
| **技术标编辑（Web）**            | ✅ 主导       | ✅ 查看+批注    | ❌         |
| **AI 生成触发**               | ✅          | ❌          | ❌         |
| **成本录入**                  | ✅          | ✅          | ✅         |
| **定价决策（最终）**              | ❌          | ✅ **决策权**  | ✅ 建议权     |
| **形式审查确认**                | ✅ 执行       | ✅ 查看       | ❌         |
| **最终标书下载**                | ✅          | ✅          | ❌         |
| **复盘结果录入**                | ✅          | ✅          | ❌         |
| **数据看板**                  | ✅ 项目级      | ✅ 公司级（全部）  | ✅ 财务级     |
| **系统管理（资质库/业主库）**         | ❌          | ✅          | ❌         |
| **AI 模型训练触发**             | ❌          | ✅          | ❌         |

七、关键算法逻辑（伪代码）
7.1 精确资质匹配算法（Week 1-2）

    def exact_match(ocr_text: str, standard_cert: dict) -> bool:
    cleaned = normalize(ocr_text)  # 去空格、统一中文数字
    
    # 1. 必须包含所有 required_keywords
    for kw in standard_cert.required_keywords:
        if kw not in cleaned:
            return False
    
    # 2. 必须不包含任何 exclude_keywords（防止经营证误判为生产证）
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

7.2 综合中标概率计算（Week 2 启发式）

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

7.3 RAG 检索算法（Week 3）

    def hybrid_retrieval(query_vector, project_context, top_k=5):
    # 向量相似度 + 元数据过滤 + 质量加权
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

历史文件冷启动AI模型训练流程设计
投标智能辅助系统（TIS）总体产品需求文档（PRD）
版本：v1.0
日期：2026-03-24
适用对象：开发团队（Claude）、业务负责人、系统架构师
一、项目概述
1.1 产品定位
投标智能辅助系统（Tender Intelligence System, TIS） 是专为食材配送与物业服务企业设计的智能投标决策与标书生成平台。
核心价值主张：
有关系项目：通过系统化响应确保 100% 中标（不漏分、不废标）
无关系项目：通过极致技术标优化 + 精准博弈定价，最大化中标概率，打破"无关系不中标"的行业魔咒
1.2 业务背景
当前痛点：投标行业水很深，无内幕关系很难中标；标书制作耗时（3-7天/份）；资质管理混乱（扫描件易过期）
数据基础：初期基于 11 份历史投标文件（5 中标 + 6 未中标）冷启动，后续持续自进化
技术栈：PostgreSQL + pgvector、PaddleOCR、DeepSeek API、FastAPI、Vue3、Docker
1.3 成功指标
短期（3个月）：无关系项目中标率提升 30%，有关系项目废标率降至 0%
中期（6个月）：标书制作时间缩短 50%（从 5 天到 2.5 天）
长期（12个月）：积累 100+ 项目数据，AI 定价模型准确率达到 80%+
二、系统架构总览
2.1 整体业务闭环
plain
复制
[Week 1] 文件智能解析          [Week 2] 初筛决策           [Week 3] 标书生成
├─ PDF/Word 上传              ├─ 资质精确匹配             ├─ RAG 检索知识库
├─ 扫描件 OCR (PaddleOCR)     ├─ 时间充裕度计算           ├─ LLM 生成技术方案
├─ 并排确认界面               ├─ 业主画像匹配             ├─ 人机协同编辑器
└─ 结构化数据入库             ├─ 选项A审批流              └─ 评分点索引生成
                              └─ 智能评估报告             └─ 业绩案例关联

[Week 4] 博弈定价决策         [Week 5] 形式审查与输出      [Week 6] 复盘与进化
├─ 成本录入（三角色）          ├─ 自动审查 vs 招标文件      ├─ 中标 DNA 提取
├─ 概率-利润矩阵              ├─ PDF 高亮标注风险点        ├─ 废标陷阱入库
├─ 定价版本控制               ├─ 强制拦截生成              ├─ 废弃草稿复活
└─ AI 模型冷启动/训练          ├─ Word 标书生成            └─ 知识库自清理
                              └─ 封装指南打印

[Week 7] 多项目协同           [Week 8] 智能化进阶
├─ 资源冲突检测               ├─ 竞争对手自动驾驶舱
├─ 日历与优先级               ├─ ML 定价模型训练
├─ 数据看板（老板驾驶舱）       ├─ 移动端小程序
└─ 封装打印优化               └─ RAG Chatbot 知识问答
2.2 技术架构图
plain
复制
┌──────────────────────────────────────────────────────────────┐
│                        用户层                               │
│   标书专员（执行+审批）   老板（监督+推翻）   财务（成本+建议）  │
└──────────────────┬─────────────────────────────┬───────────┘
                   │                             │
┌──────────────────▼─────────────┐  ┌───────────▼────────────┐
│       应用层 (FastAPI)          │  │      前端 (Vue3)        │
│  ┌──────────────────────────┐  │  │  ┌──────────────────┐ │
│  │ Week 1: Document Parser │  │  │  │ Week 3: Editor   │ │
│  │ Week 2: Evaluation Svc  │  │  │  │ Week 4: Pricing  │ │
│  │ Week 3: Generation Svc  │  │  │  │ Week 5: Review   │ │
│  │ Week 4: Pricing Engine  │  │  │  │ Week 7: Dashboard│ │
│  │ Week 5: Formal Review   │  │  │  └──────────────────┘ │
│  └──────────────────────────┘  │  └──────────────────────┘
└──────────┬────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────┐
│                      AI/ML 层                               │
│  PaddleOCR (文档识别)    DeepSeek LLM (生成/解析)            │
│  pgvector (向量检索)     XGBoost (Week 8 定价模型)           │
└──────────┬────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────┐
│                      数据层                                 │
│  PostgreSQL (业务数据)      Redis (缓存)      MinIO (文件)    │
│  ├─ projects               ├─ session      ├─ PDF/Word    │
│  ├─ standard_certs         └─ queue         ├─ Images      │
│  ├─ knowledge_chunks (pgvector)               └─ Output     │
│  └─ bid_outcomes                                            │
└─────────────────────────────────────────────────────────────┘
三、核心业务逻辑（全流程详解）
3.1 项目全生命周期状态机
plain
复制
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
3.2 双模式业务逻辑（有内幕 vs 无内幕）
表格
维度	无内幕项目（破局模式）	有内幕项目（稳赢模式）
初筛策略	极致优化，技术标拿满商务分	标准响应，确保不废标即可
技术标生成	AI 全自动（RAG top_k=5）
差异化超越（24h→12h+2h）	专员录入要点引导
RAG top_k=3，贴合业主要求
报价策略	激进低价（成本+2%）赌技术分优势	正常利润（成本+8-15%）
形式审查	强制严格（100%检查）	同样严格（关系不能救废标）
审批流	专员审批→系统推荐 abandon 时可强制 worthy	专员审批→快速通过
3.3 关键业务规则（全局约束）
R1. 精确匹配原则（生死线）
证书名称必须精确匹配标准库编码，禁止模糊匹配
"食品经营许可证" vs "食品生产许可证" 必须区分（exclude_keywords 互斥）
"一级资质" vs "二级资质" 必须区分（等级关键词精确匹配）
R2. 审批权限（选项 A 模式）
专员拥有独立初筛审批权（worthy/unworthy），点击立即生效
老板拥有事后监督权，可随时推翻（terminate/revive），硬终止或复活
推翻操作必须填写理由，记录审计日志
R3. 强制拦截机制
形式审查存在 risk_level='fatal' 且未处理时，禁止生成最终标书（按钮灰色）
资质有效期 < 开标日期时，中标概率强制归零，专员标记 worthy 需填写覆盖理由
报价 > 预算限价时，强制二次确认
R4. 知识库进化
中标项目技术标段落 quality_score +20，优先参与 RAG 检索
usage_count=0 且 3 个月未使用的知识块标记 deprecated
废标原因自动提取，更新形式审查清单模板
四、数据库设计（完整 ER 关系）
4.1 核心实体关系图
plain
复制
projects (1)
  ├─ tender_documents (1:1) 招标文件解析
  ├─ bid_documents (1:N) 投标文件（资质/技术/商务）
  │    └─ document_images (1:N) 提取的图片
  │         └─ ocr_extractions (1:N) OCR识别结果
  ├─ bid_evaluation_reports (1:N) 初筛报告（版本控制）
  ├─ tech_proposal_tasks (1:N) 技术标生成任务
  ├─ pricing_decisions (1:N) 定价决策（版本控制）
  ├─ formal_review_items (1:N) 形式审查检查项
  ├─ bid_outcomes (1:1) 投标结果（复盘）
  └─ approval_logs (1:N) 审批审计日志

owner_profiles (N) ───┐
                      ├── 关系指数计算
standard_certs (N) ───┘
                      ├── 资质匹配

knowledge_chunks (N) ───┐
                        ├── RAG检索
document_images (N) ────┘
4.2 关键表结构汇总（Week 1-8 整合）
基础层：
projects: 项目主表（状态机、关系标记）
users: 用户表（专员/老板/财务，RBAC）
owner_profiles: 业主画像库（历史合作、关系指数）
文档层：
tender_documents: 招标文件解析结果（JSON结构化）
bid_documents: 投标文件元数据
document_images: PDF提取的图片（OCR状态追踪）
ocr_extractions: OCR结构化数据（字段级，含坐标）
知识层：
standard_certifications: 标准资质库（精确匹配规则、关键词、正则）
knowledge_chunks: 知识库分块（向量 1536 维，metadata JSONB）
performance_cases: 业绩案例库（文字描述+扫描件路径）
业务层：
bid_evaluation_reports: 初筛报告（资质匹配度、时间分析、概率计算）
tech_proposal_tasks: 技术标生成任务（RAG结果、编辑版本、确认状态）
scoring_indexes: 评分点索引表（专家友好导航）
决策层：
pricing_decisions: 定价决策（成本基线、三级价格、差异原因）
formal_review_items: 形式审查检查项（系统生成+人工补充，PDF坐标高亮）
复盘层：
bid_outcomes: 投标结果（中标/未中标/废标，根因分析）
winning_dna: 中标 DNA 提取（高分段落标记）
disqualification_traps: 废标陷阱库（自动更新检查清单）
discarded_projects: 废弃项目库（支持复活）
系统层：
approval_logs: 审批审计日志（选项 A 模式全记录）
automation_tasks: 自动化任务（爬虫、模型训练定时）
dashboard_metrics: 数据看板指标（预计算）
五、功能模块详细设计（Week 1-8 整合）
5.1 Week 1: 文档智能解析引擎 (DIE)
核心功能：
多格式支持：PDF（含扫描件）/ Word 上传，MD5 去重
图像提取：PyMuPDF 提取内嵌图片，分类（营业执照/资质/合同/身份证）
OCR 识别：PaddleOCR 本地部署，中文优化，方向分类
结构化提取：
营业执照：统一信用代码（18位正则）、经营范围、有效期
资质证书：证书名称（标准化清洗）、编号、颁发机构、有效期、等级（一级/二级）
合同页：金额、甲方、日期
并排确认界面：左（PDF原图）-中（缩略图导航）-右（结构化表单，低置信度标红）
精确匹配预览：对比 standard_certifications，显示疑似证书类型建议
关键技术点：
日期标准化：2025年3月 → 2025-03-01
等级关键词统一：壹→一，防止 OCR 错误导致匹配失败
坐标记录：bbox_coords 存储，供 Week 5 PDF 高亮使用
5.2 Week 2: 初筛决策引擎 (SIE)
核心功能：
精确资质匹配引擎：
必须包含 keywords 检查（一个都不能少）
必须排除 excludes 检查（有一个就失败）
等级精确匹配（一级≠二级）
有效期覆盖检查（资质有效期 ≥ 开标日期）
时间充裕度计算：剩余天数分级（expired/urgent/tight/normal/relaxed）
业主画像匹配：历史合作次数 → 关系指数（0=无，>0=有）
成本估算：历史相似项目平均 × 通胀，或预算×75%（冷启动）
综合概率计算：启发式算法（资质40% + 时间20% + 关系30% + 其他10%）
选项 A 审批流：
专员独立审批（worthy/unworthy），立即生效
老板监督台（事后查看，可推翻 terminate/revive）
审计日志全记录
界面设计：
初筛报告页：资质匹配度环形图、时间充裕度标签、风险雷达图（致命/警告）
老板监督台：今日已审批列表、放弃库（可复活）、推翻操作按钮
5.3 Week 3: 智能标书生成引擎 (IGE)
核心功能：
双模式 RAG 检索：
无内幕：top_k=5，最大化召回，策略 ABCD（差异化超越）
有内幕：top_k=3，精准匹配专员录入要点（标签+自然语言）
Prompt 工程策略：
A. 差异化超越：标准 24h → 承诺 12h+2h 应急
B. 证据链完整：数据+流程图+案例引用
C. 专家友好：【评分点响应】标记，加粗表格
D. 业主语境：学校（守护师生健康）vs 政府（规范严谨）
人机协同编辑器：
类 Notion 富文本编辑器，段落级操作
AI 续写/改写/扩写（选中段落触发）
业绩案例拖拽插入（自动关联匹配案例）
版本历史对比（AI 生成 vs 人工修改）
评分点索引生成：自动对应章节页码，专家快速定位
数据结构：
generated_content: JSON 数组（章节标题+内容+来源引用+案例关联）
scoring_indexes: 评分项与章节页码映射表
5.4 Week 4: 博弈定价决策系统 (IPDS)
核心功能：
成本录入：三角色可录（专员/老板/财务），版本控制（v1, v2...），记录修改理由
定价策略矩阵：
激进（成本+2%）：高概率低利润
平衡（成本+8%）：中等概率中等利润
保守（成本+15%）：低概率高利润
最优：期望收益 = 利润 × 概率，最大化
概率计算：
冷启动（<20 项目）：Week 2 启发式算法
Week 8 ML 模型：XGBoost，特征（预算、关系指数、竞争烈度）
版本控制：记录三级价格（系统建议/财务建议/老板决策），差异 >5% 强制填写原因
限价拦截：报价 > 预算价时红色警告，超限时禁止提交
界面设计：
定价驾驶舱：成本基线面板、三种策略对比表格、博弈曲线图、历史对标数据
5.5 Week 5: 形式审查与输出系统 (FRCS)
核心功能：
自动审查引擎：
对比招标文件 vs 投标文件（OCR 结果）
检查项：资质有效性（过期？）、签字盖章完整性、密封要求、报价合规
双视图展示：
列表视图：检查项清单（通过/警告/致命）
PDF 高亮视图：在原始 PDF 上红框/黄框标注风险位置（使用 Week 1 坐标）
人机协同确认：
确认通过：认可系统判断
修正：系统误判时人工纠正（记录到审计）
删除：系统误报时删除（记录原因优化算法）
全局补充：新增系统未识别风险
强制拦截：存在未处理致命风险时，生成最终标书按钮灰色禁用
输出生成：
Word 合并：技术标（Week 3）+ 商务标报价（Week 4）
评分点索引页（封面后第 2 页）
封装指南：密封标签打印页、封装清单（带二维码手机核对）
5.6 Week 6: 复盘与知识进化系统 (RKE)
核心功能：
结果录入：中标/未中标/废标，中标价、竞争对手、废标原因
自动复盘：
废标：对比 Week 5 审查记录，定位失败点（形式审查？资质？）
未中标：价格分析（我们的折扣 vs 中标价）、技术标质量推断
中标：提取中标 DNA（高分段落标记，quality_score +20）
知识库进化：
热门知识加权（中标贡献）
冷门知识清理（usage_count=0 且 3 个月未用）
废标陷阱库更新（出现 2 次以上自动新增检查项模板）
废弃草稿复活：检测到项目重招（名称相似+业主相同+时间近）→ 自动提醒历史原因 → 一键复活技术标段落
5.7 Week 7: 多项目协同与数据看板 (Orchestration)
核心功能：
资源冲突检测：专员同时负责 >3 项目时警告，时间冲突检测（开标日重叠）
日历视图：老板看全公司，专员看自己，财务看待定价
老板驾驶舱 KPI：
中标率趋势（总体/有内幕/无内幕）
财务漏斗（投标额 vs 中标额 vs 成本）
风险预警（中标概率 <30% 但未放弃的项目）
封装优化：打印设置（正本/副本、双面/单面）、密封标签生成、二维码核对清单
5.8 Week 8: 智能化进阶 (Advanced AI)
核心功能：
竞争对手自动驾驶舱：
每日爬取政府采购网中标公告
监控特定对手（如 XX 餐饮）的投标频率、胜率、报价下浮率趋势
预警：对手报名参加你跟踪的项目时立即推送
ML 定价模型：
基于 20+ 项目数据训练 XGBoost
特征：预算、地区、类型、关系指数、竞争烈度
可解释性输出（特征重要性：关系 30%、预算 25%...）
移动端小程序：
手机拍照上传招标文件（OCR 自动创建草稿）
语音录入定价决策（ASR 转文字保存）
开标前 2 小时提醒 + 封装清单扫码核对
RAG Chatbot：知识问答（"ISO22000 vs HACCP 区别？"），引用历史案例回答
六、用户角色与权限矩阵（RBAC）
表格
功能模块	标书专员（执行者）	老板（决策/监督）	财务（成本/建议）
项目创建/上传	✅	✅	❌
文件解析确认	✅	✅（查看）	❌
初筛报告查看	✅	✅	✅
初筛审批（worthy/unworthy）	✅ 独立审批	✅ 事后推翻	❌
内幕/无内幕标记	✅	✅	❌
技术标编辑（Web）	✅ 主导	✅ 查看+批注	❌
AI 生成触发	✅	❌	❌
成本录入	✅	✅	✅
定价决策（最终）	❌	✅ 决策权	✅ 建议权
形式审查确认	✅ 执行	✅ 查看	❌
最终标书下载	✅	✅	❌
复盘结果录入	✅	✅	❌
数据看板	✅ 项目级	✅ 公司级（全部）	✅ 财务级
系统管理（资质库/业主库）	❌	✅	❌
AI 模型训练触发	❌	✅	❌
七、关键算法逻辑（伪代码）
7.1 精确资质匹配算法（Week 1-2）

    def exact_match(ocr_text: str, standard_cert: dict) -> bool:
    cleaned = normalize(ocr_text)  # 去空格、统一中文数字
    
    # 1. 必须包含所有 required_keywords
    for kw in standard_cert.required_keywords:
        if kw not in cleaned:
            return False
    
    # 2. 必须不包含任何 exclude_keywords（防止经营证误判为生产证）
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
7.2 综合中标概率计算（Week 2 启发式）

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
7.3 RAG 检索算法（Week 3）

    def hybrid_retrieval(query_vector, project_context, top_k=5):
    # 向量相似度 + 元数据过滤 + 质量加权
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

7.4 定价期望收益最大化（Week 4）

    def search_optimal_price(cost, budget, win_prob_func):
    best_expectation = 0
    optimal_price = cost * 1.05
    
    for markup in [0.02, 0.03, 0.05, 0.08, 0.10, 0.12, 0.15]:
        price = cost * (1 + markup)
        if price > budget * 0.95:  # 限价约束
            continue
        
        prob = win_prob_func(price)  # ML 或规则模型
        profit = price - cost
        expectation = profit * prob
        
        if expectation > best_expectation:
            best_expectation = expectation
            optimal_price = price
    
    return optimal_price, best_expectation


八、非功能性需求
8.1 性能指标
并发：支持 3 个标书专员同时操作（3 并发用户）
响应时间：文件解析 < 30 秒（50MB PDF），RAG 检索 < 2 秒，页面加载 < 3 秒
存储：MinIO 对象存储，支持 1TB 标书文件历史归档
8.2 安全与合规
数据隔离：项目级权限隔离（专员 A 看不到专员 B 的项目，除非授权）
审计：所有审批操作（特别是老板推翻）记录不可篡改日志（approval_logs）
备份：每日自动备份 PostgreSQL，保留 30 天
OCR 数据：敏感资质信息（身份证号等）加密存储，展示时脱敏
8.3 部署与运维
容器化：Docker Compose 一键启动（PostgreSQL + Redis + MinIO + FastAPI + PaddleOCR）
环境变量：DeepSeek API Key、数据库连接串、MinIO 密钥通过环境变量注入
监控：Health check 接口 /health，关键错误告警（Slack/钉钉）
九、实施路线图（MVP → 成熟）
Phase 1: MVP（Week 1-6）- 核心闭环
目标：实现从文件上传到复盘的全流程跑通，支持 11 份历史文件导入
关键交付：精确资质匹配、初筛审批、技术标生成、定价决策、形式审查拦截
用户：老板 + 1 个专员 + 1 个财务内部使用
Phase 2: 优化（Week 7）- 规模化
目标：支持多项目并行，数据看板辅助决策
关键交付：资源冲突检测、封装打印优化、系统管理后台
Phase 3: 智能化（Week 8）- 自动化
目标：减少人工操作 50%，实现数据驱动的投标策略
关键交付：竞争对手爬虫、ML 定价模型、移动端小程序、知识问答机器人
十、给开发团队的最终指令
Claude 开发指引：
严格遵循数据库设计：外键关系、JSONB 字段结构、check 约束必须一致
Week 1 是基础：PaddleOCR 部署和精确匹配算法必须 100% 可靠，否则 Week 2-8 都是空中楼阁
选项 A 审批流：务必实现"专员审批立即生效 + 老板事后推翻"的状态机，不要做成多级审批流
Prompt 工程：Week 3 的 ABCD 策略必须体现在 DeepSeek 的 system prompt 中
渐进式交付：每完成一个 Week，必须能通过该周的验收 checklist 才能进入下一周
业务验收标准：
上传 1 份真实招标文件（含扫描资质），系统能正确识别过期证书并标红
专员标记 worthy 后，老板在监督台看到后点击"推翻终止"，项目立即停止并通知专员
生成 1 份完整技术标 Word，包含评分点索引和业绩案例引用
文档版本控制：
当前版本：v1.0（2026-03-24）
下次评审：Week 3 完成后评审技术标生成质量，必要时调整 Prompt 策略