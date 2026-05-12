投标智能辅助系统（TIS）总体框架文档
Tender Intelligence System - Master Architecture Document
版本：v1.0 Final
日期：2026-03-24
状态：待开发（Week 1-8 完整 roadmap）

一、系统定位与商业逻辑
1.1 核心命题
打破"无关系不中标"的行业魔咒，通过系统化能力将无关系项目中标率提升 30%+，有关系项目废标率降至 0%。
1.2 双模式战略
| 维度        | 有关系项目（稳赢模式）       | 无关系项目（破局模式）              |
| --------- | ----------------- | ------------------------ |
| **策略核心**  | 确保 100% 不废标，标准响应  | 极致优化，技术标拿满商务分，价格博弈       |
| **技术标生成** | 专员录入要点 → AI 定制化生成 | AI 全自动（RAG 最大化召回）        |
| **报价策略**  | 正常利润（成本+8-15%）    | 激进低价（成本+2%）赌技术分优势        |
| **审批流**   | 快速通过              | 系统建议 abandon 时可强制 worthy |

1.3 数据飞轮
11份历史文件（冷启动）→ 系统使用后积累数据 → 知识库进化 → AI模型训练（Week 8）→ 更准中标率 → 更多数据
二、总体业务架构（全流程）
2.1 八阶段闭环流程
Week 1: 感知层（Document Intelligence）
PDF/Word 上传 → 扫描件 OCR（PaddleOCR）→ 结构化提取（营业执照/资质/合同）→ 并排确认 → 精确匹配标准库
Week 2: 决策层（Screening & Evaluation）
初筛报告生成（资质匹配度/时间/业主画像/成本估算）→ 选项 A 审批流（专员独立审批+老板事后推翻）→ worthy/unworthy 分流
Week 3: 生成层（Content Generation）
RAG 检索知识库 → 双模式生成（无内幕全自动 vs 有内幕引导）→ 人机协同编辑器 → 评分点索引 → 业绩案例关联
Week 4: 定价层（Pricing Intelligence）
成本录入（三角色）→ 博弈矩阵（激进/平衡/保守）→ 期望收益最大化 → 版本控制（系统/财务/老板三级价格）
Week 5: 风控层（Formal Review）
自动审查（投标文件 vs 招标文件）→ PDF 高亮标注风险 → 强制拦截（致命风险未处理禁止生成）→ Word 封装输出
Week 6: 进化层（Knowledge Evolution）
中标 DNA 提取 → 废标陷阱入库 → 废弃草稿复活 → 知识库清理（冷门淘汰）→ 形式审查模板更新
Week 7: 管理层（Orchestration）
多项目并行冲突检测 → 日历视图 → 老板驾驶舱（KPI/漏斗/风险预警）→ 封装打印优化
Week 8: 自动驾驶层（Advanced AI）
竞争对手爬虫监控 → ML 定价模型（XGBoost）→ 移动端小程序 → RAG Chatbot 知识问答
2.2 关键状态机（项目生命周期）
uploaded → parsed → evaluation_ready → approved_by_specialist → generating_documents 
    → awaiting_pricing → awaiting_review → completed → bid_outcome → knowledge_evolution
         ↓（老板推翻）              ↓（废弃草稿库）
    terminated_by_boss ← revived → reactivated
三、技术架构总览
3.1 三层架构
数据层（Data Tier）
PostgreSQL + pgvector：业务数据 + 向量检索（1536 维）
Redis：缓存 + 消息队列
MinIO：对象存储（PDF/Word/图片/输出文件）
AI 层（Intelligence Tier）
PaddleOCR：本地部署，中文扫描件识别（方向分类 + 高精版）
DeepSeek API：文本生成（技术标）、结构化提取（Prompt 工程）
XGBoost（Week 8）：定价预测模型，特征（预算/关系/竞争烈度）
应用层（Application Tier）
FastAPI：Python 异步后端，RESTful API
Vue 3 + Element Plus：管理端（PC 富文本编辑器）
微信小程序（Week 8）：移动端轻量操作
3.2 核心技术栈选型理由
| 技术                      | 用途     | 选型理由                          |
| ----------------------- | ------ | ----------------------------- |
| **PostgreSQL+pgvector** | 向量数据库  | RAG 检索必需，精确相似度计算              |
| **PaddleOCR**           | 中文 OCR | 比 Tesseract 中文准确率高 20%，支持 GPU |
| **DeepSeek**            | LLM    | 国内 API 稳定，成本低，支持 JSON 输出      |
| **FastAPI**             | 后端     | 异步高性能，自动生成 Swagger 文档         |
| **XGBoost**             | ML 模型  | 可解释性强（特征重要性），适合投标决策           |

四、数据架构（核心实体）
4.1 五大核心域
1. 项目域（Project Domain）
projects (主表) ←→ tender_documents (招标文件解析)
      ↓
bid_documents (投标文件) ←→ document_images (扫描件) ←→ ocr_extractions (结构化数据)
2. 知识域（Knowledge Domain）
standard_certifications (标准资质库，精确匹配规则)
knowledge_chunks (向量知识库，RAG 检索，metadata JSONB)
performance_cases (业绩案例库，文字+扫描件路径)
3. 决策域（Decision Domain）
bid_evaluation_reports (初筛报告，资质匹配度/概率计算)
tech_proposal_tasks (技术标生成，RAG 结果+编辑版本)
pricing_decisions (定价决策，三级价格+差异原因)
formal_review_items (形式审查检查项，PDF 坐标+风险等级)
4. 流程域（Workflow Domain）
approval_logs (审批审计，选项 A 模式全记录)
discarded_projects (废弃项目库，支持复活)
project_schedules (Week 7 资源调度，里程碑+冲突检测)
5. 复盘域（Evolution Domain）
bid_outcomes (投标结果，中标/未中标/废标根因)
winning_dna (中标 DNA，高分段落标记)
disqualification_traps (废标陷阱库，自动更新检查清单)
4.2 关键数据流向
上游：document_images → ocr_extractions → standard_certifications（精确匹配）→ bid_evaluation_reports（Week 2）
中游：knowledge_chunks (RAG) → tech_proposal_tasks (生成) → pricing_decisions (定价) → formal_review_items (审查)
下游：bid_outcomes (结果) → winning_dna/disqualification_traps (知识进化) → 更新上游知识库

五、功能模块矩阵（Week 1-8）
| Week  | 模块名                        | 核心功能                                                                         | 关键交付物                                                                   | 依赖        |
| ----- | -------------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------------------- | --------- |
| **1** | **DIE**<br>文档智能解析          | • PDF/Word 上传与存储<br>• 扫描件 OCR（PaddleOCR）<br>• 并排确认界面（PDF+OCR+编辑）<br>• 精确匹配预览 | • `document_images` 表<br>• `ocr_extractions` 表<br>• 可运行的 Docker 环境      | 无         |
| **2** | **SIE**<br>初筛决策引擎          | • 精确资质匹配（非模糊）<br>• 时间充裕度计算<br>• 业主画像匹配（关系指数）<br>• 选项 A 审批流（专员+老板）            | • `bid_evaluation_reports` 表<br>• `approval_logs` 表<br>• 初筛报告界面         | Week 1    |
| **3** | **IGE**<br>智能标书生成          | • RAG 检索（pgvector）<br>• 双模式生成（Auto/Guided）<br>• 人机协同编辑器（段落级）<br>• 评分点索引生成    | • `tech_proposal_tasks` 表<br>• `scoring_indexes` 表<br>• Web 富文本编辑器      | Week 1, 2 |
| **4** | **IPDS**<br>博弈定价决策         | • 成本录入（版本控制）<br>• 概率-利润矩阵<br>• 定价版本控制（三级价格）<br>• 限价拦截                        | • `pricing_decisions` 表<br>• 定价驾驶舱界面                                    | Week 2, 3 |
| **5** | **FRCS**<br>形式审查与输出        | • 自动审查对比<br>• PDF 高亮标注<br>• 强制拦截生成<br>• Word 封装输出                            | • `formal_review_items` 表<br>• `final_bid_documents` 表<br>• 封装指南        | Week 3, 4 |
| **6** | **RKE**<br>复盘与进化           | • 中标 DNA 提取<br>• 废标陷阱入库<br>• 废弃草稿复活<br>• 知识库清理                               | • `bid_outcomes` 表<br>• `winning_dna` 表<br>• `disqualification_traps` 表 | Week 1-5  |
| **7** | **Orchestration**<br>多项目协同 | • 资源冲突检测<br>• 日历视图<br>• 老板驾驶舱（KPI）<br>• 封装打印优化                               | • `project_schedules` 表<br>• `dashboard_metrics` 表<br>• 数据看板            | Week 1-6  |
| **8** | **Advanced AI**<br>智能化进阶   | • 竞争对手爬虫<br>• ML 定价模型（XGBoost）<br>• 移动端小程序<br>• RAG Chatbot                  | • `competitor_monitoring` 表<br>• `pricing_ml_models` 表<br>• ML Pipeline | Week 1-7  |

六、关键业务规则（硬性约束）
6.1 精确匹配原则（生死线）
证书名称：必须满足 required_keywords（全含）+ exclude_keywords（全无）
等级精确："建筑工程施工总承包一级" 的 exclude_keywords 必须包含 ["二级", "三级"]
有效期拦截：资质有效期 < 开标日期时，中标概率强制归零，标记 worthy 需填写覆盖理由
6.2 审批权限（选项 A）
专员：独立审批 worthy/unworthy，点击立即生效，无需等待老板
老板：事后监督，可随时推翻（terminate/revive），推翻必须填写理由并记录审计日志
生效顺序：专员审批 → 项目立即进入下一阶段 → 老板收到通知但不阻断流程
6.3 生成拦截原则
形式审查：存在 risk_level='fatal' 且 specialist_status='pending' 时，生成最终标书 按钮强制禁用
定价拦截：报价 > 预算限价时，必须二次确认；报价 < 成本时，禁止提交
资质拦截：缺少强制资质时，系统建议 abandon，专员强制 worthy 需详述理由
6.4 知识库进化
加权：中标项目技术标段落 quality_score +20，优先参与 RAG 检索
淘汰：usage_count=0 且 3 个月未使用，标记 deprecated
复活：废弃草稿 12 个月内可复活，超过自动清理
七、实施路线图与验收
7.1 分阶段交付
Phase 1: Foundation（Week 1-2）- 决策引擎
目标：跑通"上传→解析→初筛→审批"核心闭环
验收：
[ ] 上传含扫描营业执照的 PDF，OCR 识别出统一信用代码（18位正则验证）
[ ] 资质有效期 2025-12-31，开标 2026-04-15，系统标红提示"已过期"
[ ] 专员点击 worthy 立即进入 Week 3 任务，老板监督台显示记录并可推翻
Phase 2: Generation（Week 3-5）- 标书工厂
目标：实现"技术标生成→定价→审查→输出"生产流水线
验收：
[ ] 无内幕项目自动生成 8000+ 字技术标，含评分点索引和业绩案例引用
[ ] 有内幕项目录入"必须使用双汇品牌"，生成内容出现双汇及供应链保障
[ ] 形式审查检测到签字缺失，PDF 高亮标注红色，未处理时禁止生成 Word
Phase 3: Evolution（Week 6-8）- 智能闭环
目标：系统具备自进化能力，实现数据驱动的投标策略
验收：
[ ] 中标项目自动提取 DNA，后续 RAG 检索时优先推荐
[ ] 积累 20+ 项目后，ML 定价模型准确率 >75%
[ ] 手机拍照上传招标文件，自动创建草稿项目
7.2 技术债务控制
Week 1 必须完成：Docker 一键启动、数据库迁移脚本、PaddleOCR 正确部署
Week 3 必须完成：向量索引（ivfflat）、RAG 检索阈值调优（cosine > 0.75）
Week 5 必须完成：PDF 高亮坐标系统（PyMuPDF annot）与 Word 生成（python-docx）对接

文档控制：
主版本：v1.0（2026-03-24）
更新策略：每完成一个 Week，根据实际开发调整下一周细节，但总体框架不变
争议解决：业务逻辑以本框架为准，技术实现细节由 Claude 根据最佳实践调整