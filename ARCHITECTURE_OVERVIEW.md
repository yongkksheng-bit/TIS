TIS 整体代码架构（Tender Intelligence System - Code Architecture）
版本：v1.0
技术栈：Python 3.11 + FastAPI + PostgreSQL + pgvector + PaddleOCR + DeepSeek
架构模式：分层架构（Layered Architecture）+ 领域驱动设计（DDD Lite）
tis-project/
├── alembic/                          # 数据库迁移（Alembic）
│   ├── versions/                     # 迁移脚本（按Week分）
│   │   ├── w001_initial_schema.py    # Week 1: 基础表
│   │   ├── w002_evaluation_engine.py # Week 2: 初筛相关
│   │   ├── w003_generation_rag.py    # Week 3: RAG向量库
│   │   └── w004_pricing_ml.py        # Week 4+: 定价与ML
│   └── env.py

├── app/                              # 主应用目录
│   ├── __init__.py
│   ├── main.py                       # FastAPI应用入口
│   ├── config.py                     # 全局配置（Pydantic Settings）
│   ├── dependencies.py               # FastAPI依赖注入（DB、Redis、CurrentUser）
│   │
│   ├── api/                          # API层（路由定义）
│   │   ├── __init__.py
│   │   ├── v1/                       # API版本控制
│   │   │   ├── __init__.py
│   │   │   ├── endpoints/            # 按领域分端点
│   │   │   │   ├── auth.py           # 登录/权限（JWT）
│   │   │   │   ├── projects.py       # 项目基础CRUD
│   │   │   │   ├── documents.py      # Week 1: 文件上传/OCR
│   │   │   │   ├── evaluation.py     # Week 2: 初筛报告/审批流
│   │   │   │   ├── generation.py     # Week 3: 技术标生成/编辑
│   │   │   │   ├── pricing.py        # Week 4: 定价决策
│   │   │   │   ├── formal_review.py  # Week 5: 形式审查
│   │   │   │   ├── outcomes.py       # Week 6: 复盘结果
│   │   │   │   ├── dashboard.py      # Week 7: 数据看板
│   │   │   │   └── admin.py          # Week 7: 系统管理
│   │   │   └── router.py             # v1路由聚合
│   │   └── deps.py                   # API依赖（权限检查等）
│   │
│   ├── core/                         # 核心业务逻辑（Service Layer）
│   │   ├── __init__.py
│   │   ├── week1_document/           # Week 1: 文档解析领域
│   │   │   ├── __init__.py
│   │   │   ├── parser.py             # PDF/Word解析服务
│   │   │   ├── ocr_engine.py         # PaddleOCR封装
│   │   │   ├── image_classifier.py   # 图片类型分类（LLM/规则）
│   │   │   ├── extraction_normalizer.py  # 标准化清洗
│   │   │   └── confirmation_service.py   # 并排确认逻辑
│   │   │
│   │   ├── week2_evaluation/         # Week 2: 初筛决策领域
│   │   │   ├── __init__.py
│   │   │   ├── qualification_matcher.py    # 精确匹配算法（核心）
│   │   │   ├── report_generator.py         # 初筛报告生成
│   │   │   ├── approval_workflow.py       # 选项A审批流实现
│   │   │   └── owner_profiler.py          # 业主画像计算
│   │   │
│   │   ├── week3_generation/         # Week 3: 标书生成领域
│   │   │   ├── __init__.py
│   │   │   ├── rag_engine.py         # RAG检索（pgvector）
│   │   │   ├── prompt_engineering.py # ABCD策略Prompt构建
│   │   │   ├── tech_proposal_service.py    # 技术标生成服务
│   │   │   ├── editor_service.py     # 版本控制/AI改写
│   │   │   └── scoring_indexer.py    # 评分点索引生成
│   │   │
│   │   ├── week4_pricing/            # Week 4: 定价决策领域
│   │   │   ├── __init__.py
│   │   │   ├── cost_estimation.py    # 成本估算（历史/比例）
│   │   │   ├── game_theory_model.py  # 博弈模型（冷启动/ML）
│   │   │   ├── pricing_service.py    # 定价版本控制
│   │   │   └── version_control.py    # 三级价格差异追踪
│   │   │
│   │   ├── week5_formal_review/      # Week 5: 形式审查领域
│   │   │   ├── __init__.py
│   │   │   ├── checklist_generator.py    # 检查项动态生成
│   │   │   ├── pdf_highlighter.py        # PDF高亮渲染（PyMuPDF）
│   │   │   ├── review_interceptor.py     # 强制拦截逻辑
│   │   │   └── output_generator.py       # Word最终生成
│   │   │
│   │   └── week6_evolution/          # Week 6: 知识进化领域
│   │       ├── __init__.py
│   │       ├── dna_extractor.py        # 中标DNA提取
│   │       ├── trap_updater.py         # 废标陷阱库更新
│   │       ├── draft_revival.py        # 废弃草稿复活
│   │       └── knowledge_cleaner.py    # 冷门知识清理
│   │
│   ├── models/                       # 数据模型层（SQLAlchemy）
│   │   ├── __init__.py
│   │   ├── base.py                   # 基类（id, created_at等）
│   │   ├── user.py                   # 用户/角色
│   │   ├── project.py                # 项目主表（状态机）
│   │   ├── document.py               # 文档相关（tender_documents等）
│   │   ├── ocr.py                    # OCR提取结果
│   │   ├── standard.py               # 标准资质库
│   │   ├── knowledge.py              # 知识库（pgvector）
│   │   ├── evaluation.py             # 初筛报告
│   │   ├── generation.py               # 技术标生成任务
│   │   ├── pricing.py                # 定价决策
│   │   ├── formal_review.py          # 形式审查
│   │   ├── outcome.py                # 复盘结果
│   │   └── audit.py                  # 审批日志
│   │
│   ├── schemas/                      # Pydantic模型（API出入参）
│   │   ├── __init__.py
│   │   ├── common.py                 # 通用响应（Page, Response）
│   │   ├── document.py               # Week 1
│   │   ├── evaluation.py             # Week 2
│   │   ├── generation.py             # Week 3
│   │   ├── pricing.py                # Week 4
│   │   └── formal_review.py          # Week 5
│   │
│   ├── services/                     # 基础设施服务（封装第三方）
│   │   ├── __init__.py
│   │   ├── storage.py                # MinIO/本地存储服务
│   │   ├── vector_db.py              # pgvector向量操作封装
│   │   ├── llm_client.py             # DeepSeek API封装
│   │   ├── ocr_client.py             # PaddleOCR调用
│   │   └── embedding.py              # 向量生成服务
│   │
│   └── utils/                        # 工具函数
│       ├── __init__.py
│       ├── datetime_utils.py         # 日期标准化（Week 1清洗用）
│       ├── text_similarity.py        # 文本相似度（等级匹配）
│       ├── security.py               # JWT/密码加密
│       └── exceptions.py             # 自定义异常（TISException）

├── docker/                           # Docker配置
│   ├── Dockerfile                    # 主应用镜像
│   ├── Dockerfile.paddleocr          # OCR服务独立镜像（GPU/CPU）
│   └── entrypoint.sh

├── tests/                            # 测试（按Week分）
│   ├── week1/
│   ├── week2/
│   └── conftest.py

├── notebooks/                        # Jupyter（数据分析/模型训练）
│   └── pricing_model_training.ipynb  # Week 8 ML模型

├── scripts/                          # 运维脚本
│   ├── init_db.py                    # 初始化标准资质库
│   └── backup.sh

├── requirements.txt                  # Python依赖
├── docker-compose.yml                # 全栈编排（PG+Redis+MinIO+App+OCR）
└── README.md                         # 部署指南