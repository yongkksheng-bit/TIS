Week 3 开发文档：智能标书生成引擎（RAG + 人机协同编辑系统）
文档元信息
开发周期：Week 3（5个工作日）
依赖前提：Week 1（文件解析/OCR/向量库）、Week 2（初筛报告/资质匹配）已完成
核心业务目标：实现技术标的智能生成（RAG 检索 + LLM 生成）与 Web 端段落级协同编辑
关键区分：无内幕项目（AI 全自动极致优化）vs 有内幕项目（人工录入要点 + AI 定制化生成）
交付标准：可生成含评分点索引、业绩案例关联、业主语境适配的技术标 Word 初稿，并支持 Web 端编辑确认
一、业务逻辑架构（必读）
1.1 技术标生成 Workflow（双模式）

[Week 2 初筛审批通过] 
    ↓
[标记内幕/无内幕] ← 标书专员选择
    ├─ 无内幕分支（全自动）：AI 极致优化，商务分拿满策略
    └─ 有内幕分支（定制化）：专员录入技术要点 → AI 基于要点生成
    ↓
[RAG 检索引擎] ← 从 Week 1 知识库检索相似方案（向量相似度 > 0.75）
    ├─ 检索：场景标签匹配（冷链/应急/食品安全）
    ├─ 检索：业主类型匹配（学校语境 vs 政府语境）
    ├─ 检索：评分点精准匹配（如"配送时效"对应段落）
    └─ 检索：业绩案例关联（自动匹配金额/地区/类型相近案例）
    ↓
[LLM 生成引擎] ← DeepSeek API（temperature=0.7）
    ├─ Prompt 策略 A：差异化超越（24h → 12h+2h 预备）
    ├─ Prompt 策略 B：证据链完整（数据 + 流程图 + 案例）
    ├─ Prompt 策略 C：专家友好（【评分点响应】标记）
    └─ Prompt 策略 D：业主语言（学校语境：守护师生健康）
    ↓
[生成初稿] ← JSON 结构：章节标题 + 内容 + 来源引用 + 业绩关联
    ↓
[Web 端编辑器] ← 类 Notion 富文本编辑器（段落级操作）
    ├─ 功能：AI 续写/改写/扩写（选中段落触发）
    ├─ 功能：业绩案例拖拽插入（从数据库选择）
    ├─ 功能：评分点对应自检（检查清单打钩）
    └─ 功能：版本历史对比（显示 AI 生成 vs 人工修改）
    ↓
[专员确认] ← 所有章节标记"完全响应"后，确认进入 Week 4 定价
    ↓
[更新知识库] ← 确认后的技术标段落进入知识库（quality_score 初始 50）
1.2 关键业务规则（硬性约束）
规则1：差异化生成策略
无内幕项目：generation_mode='auto'，RAG 检索 top_k=5，AI 自动融合多段落生成，强调"超越标准"（A 策略）
有内幕项目：generation_mode='guided'，RAG 检索 top_k=3，专员先录入技术要点（标签式 + 自然语言），AI 严格基于要点生成，强调"贴合需求"
规则2：知识库匹配精度
向量检索阈值：cosine similarity ≥ 0.75（低于此值视为无可靠参考，使用通用模板）
必须过滤：is_deprecated=false（Week 6 机制，Week 3 先预留字段）
权重排序：quality_score（高优先）+ usage_count（高优先）
规则3：评分点索引强制生成
生成技术标时，必须同步生成 scoring_indexes 表记录（C 策略：专家友好）
索引必须包含：评分项名称、对应章节页码、关键词匹配高亮
索引页作为技术标封面后第 2 页（目录后）
规则4：业绩案例关联
自动关联逻辑：项目类型相同 + 预算差异 < 30% + 地区相同优先
关联限制：每个章节最多关联 2 个业绩案例（防过度堆砌）
案例展示：文字描述（来自知识库）+ 扫描件路径（Week 1 数据库）
规则5：编辑锁定与版本
专员确认前：可无限次 AI 重写、人工修改
确认后：锁定编辑，如需修改需老板权限解锁（或创建新版本）
版本记录：每次 AI 重写生成新版本号，保留历史（用于 Week 6 复盘）

二、数据库表设计（SQL）

    -- 知识库分块表（Week 1 基础上增强，用于 RAG 检索）
    CREATE TABLE knowledge_chunks (
    id SERIAL PRIMARY KEY,
    chunk_type VARCHAR(50) CHECK (chunk_type IN (
        'technical_solution',   -- 技术方案段落（核心）
        'excellent_response',   -- 高分响应话术
        'owner_preference',     -- 业主偏好语料
        'case_description',     -- 业绩案例文字描述（ Week 1 业绩库关联）
        'risk_warning'          -- 风险提示/废标案例（ Week 5 形式审查用）
    )),
    content TEXT NOT NULL,              -- 文本内容（向量化）
    content_vector vector(1536),        -- DeepSeek/Kimi Embedding（pgvector）
    
    -- 元数据（检索过滤核心）
    metadata JSONB NOT NULL DEFAULT '{
        "scene": null,           -- 场景：cold_chain/delivery/emergency/food_safety/personnel
        "owner_type": null,      -- 业主：school/government/hospital/enterprise
        "project_scale": null,     -- 规模：large(>500万)/medium/small
        "service_type": null,      -- 服务：food_delivery/property/mixed
        "score_point": null,       -- 评分点：timeliness/quality/safety/emergency
        "quality_score": 50,       -- 质量分（0-100，中标后提升）
        "is_template": false,      -- 是否通用模板
        "source_project_id": null,-- 来源项目ID（溯源）
        "usage_count": 0          -- 被调用次数
    }',
    
    source_project_id INTEGER REFERENCES projects(id),  -- 来源（中标 DNA 溯源）
    is_deprecated BOOLEAN DEFAULT FALSE,  -- 是否淘汰（Week 6 清理机制）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 向量索引（必须创建，用于相似度检索）
    CREATE INDEX idx_knowledge_vector ON knowledge_chunks 
    USING ivfflat (content_vector vector_cosine_ops) 
    WITH (lists = 100);

    -- 技术标生成任务表（记录生成历史与版本）
    CREATE TABLE tech_proposal_tasks (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    generation_mode VARCHAR(20) CHECK (generation_mode IN ('auto', 'guided')), -- auto=无内幕全自动, guided=有内幕引导
    
    -- 输入配置（JSON 详细记录）
    input_config JSONB NOT NULL DEFAULT '{}',
    -- 示例结构：
    -- {
    --   "scoring_items": [{"name": "配送方案", "weight": 20, "description": "..."}], -- 来自 Week 2
    --   "owner_type": "school",
    --   "special_requirements": [                    -- 有内幕时的专员录入
    --     {"type": "tag", "key": "brand", "value": "双汇"},
    --     {"type": "text", "content": "避开上下学高峰时段配送"}
    --   ],
    --   "preferred_cases": [1, 2, 3],               -- 指定关联业绩案例ID
    --   "generation_strategy": ["A", "B", "C", "D"] -- 使用的优化策略
    -- }
    
    -- 生成结果（段落数组）
    generated_content JSONB,  -- [{
                             --   "section_id": 1,
                             --   "section_title": "冷链配送方案",
                             --   "score_weight": 20,
                             --   "content": "具体方案文本...",
                             --   "source_chunks": [101, 102, 105],  -- 引用的知识块ID
                             --   "linked_cases": [{"case_id": 5, "case_name": "XX中学2024"}],
                             --   "ai_rewrite_count": 2,
                             --   "generation_timestamp": "2026-03-24T10:00:00"
                             -- }]
    
    final_content TEXT,      -- 专员编辑后的最终 HTML/Word 内容（确认后填充）
    editor_version INTEGER DEFAULT 1,  -- 编辑版本（每次 AI 重写 +1）
    
    -- 状态流转
    status VARCHAR(20) DEFAULT 'generating' 
        CHECK (status IN ('generating', 'reviewing', 'confirmed', 'abandoned')),
    
    created_by INTEGER REFERENCES users(id),  -- 通常是标书专员
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP,
    confirmed_by INTEGER REFERENCES users(id)
    );

    -- 评分点索引表（专家友好导航）
    CREATE TABLE scoring_indexes (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    
    score_item_name VARCHAR(255),       -- 评分项名称（来自招标文件解析）
    score_weight DECIMAL(5,2),          -- 分值（如 20 分）
    corresponding_section_id INTEGER,     -- 对应技术标章节 ID
    corresponding_section_title VARCHAR(255),
    page_number INTEGER,                -- 页码（生成后填充）
    
    keyword_matches JSONB,              -- 匹配的关键词数组（用于高亮）
    is_fully_responded BOOLEAN DEFAULT FALSE,  -- 是否完全响应（专员确认）
    evidence_paragraph_ids INTEGER[],   -- 证据段落 ID 数组（关联到 content）
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 生成操作日志（用于 Week 6 复盘追踪）
    CREATE TABLE generation_logs (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES tech_proposal_tasks(id),
    operation_type VARCHAR(50),         -- 'initial_generate' / 'ai_rewrite' / 'manual_edit' / 'case_linked'
    section_id INTEGER,                 -- 操作的章节
    prompt_used TEXT,                   -- 使用的 Prompt（用于优化分析）
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd DECIMAL(8,4),              -- API 调用成本（监控用）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
三、核心算法逻辑（Python 伪代码）
3.1 RAG 检索引擎（多路召回）

    class RAGRetrievalEngine:
    def __init__(self):
        self.embedding_client = DeepSeekClient(api_key=os.getenv("DEEPSEEK_API_KEY"))
        self.vector_db = PGVector(connection_string=os.getenv("DATABASE_URL"))
    
    def hybrid_retrieval(self, query: str, project_context: dict, top_k: int = 5) -> list:
        """
        混合检索：向量相似度 + 元数据过滤 + 业务规则加权
        """
        # 1. 生成查询向量
        query_vector = self.embedding_client.embeddings.create(
            model="text-embedding-3-small",  # 或 deepseek-embedding
            input=query
        ).data[0].embedding
        
        # 2. 构建元数据过滤条件（基于项目上下文）
        owner_type = project_context.get('owner_type')  # school/government
        service_type = project_context.get('service_type')  # food_delivery
        score_point = project_context.get('score_point')  # 当前评分项关键词
        
        # 3. 向量相似度检索 SQL（带过滤）
        sql = """
        SELECT id, content, metadata, 
               content_vector <=> %s::vector as distance,
               (metadata->>'quality_score')::int as quality_score,
               (metadata->>'usage_count')::int as usage_count
        FROM knowledge_chunks
        WHERE is_deprecated = FALSE
          AND chunk_type = 'technical_solution'
        """
        params = [query_vector]
        
        # 动态过滤（硬过滤 + 软加权）
        if owner_type:
            sql += " AND (metadata->>'owner_type' = %s OR metadata->>'owner_type' IS NULL)"
            params.append(owner_type)
        
        if score_point:
            # 软匹配：优先匹配 score_point，但没有也不排除（靠向量相似度）
            pass
        
        sql += " ORDER BY (content_vector <=> %s::vector) * 0.6 + "
        sql += "       (1.0 / (1.0 + exp(-((metadata->>'quality_score')::int - 50)/10.0))) * 0.3 + "
        sql += "       LEAST((metadata->>'usage_count')::int / 100.0, 1.0) * 0.1 "
        sql += " LIMIT %s"
        params.extend([query_vector, top_k])
        
        results = db.query(sql, params)
        
        # 4. 后处理：过滤低质量（distance > 0.3 即 cosine < 0.7，视为不相关）
        filtered = [r for r in results if r['distance'] < 0.3]
        
        return filtered
    
    def retrieve_for_guided_mode(self, specialist_input: list, project_context: dict) -> list:
        """
        有内幕模式检索：更严格匹配专员录入的技术要点
        """
        # 将专员输入的 tags 和文本转换为检索 query
        queries = []
        for inp in specialist_input:
            if inp['type'] == 'tag':
                queries.append(inp['value'])  # 品牌、特殊要求关键词
            elif inp['type'] == 'text':
                # 提取关键短语（简化处理，或用 LLM 提取）
                queries.append(inp['content'][:50])
        
        all_results = []
        for q in queries:
            results = self.hybrid_retrieval(q, project_context, top_k=2)
            all_results.extend(results)
        
        # 去重 + 排序
        seen = set()
        unique_results = []
        for r in all_results:
            if r['id'] not in seen:
                unique_results.append(r)
                seen.add(r['id'])
        
        return unique_results[:3]  # 有内幕时检索更少，更精准
3.2 技术标生成引擎（双模式）

    class TechProposalGenerator:
    def __init__(self):
        self.llm = DeepSeekClient()
        self.rag = RAGRetrievalEngine()
    
    async def generate_auto_mode(self, project_id: int, scoring_item: dict) -> dict:
        """
        无内幕全自动模式：极致优化，商务分拿满（ABCD 策略）
        """
        # 1. RAG 检索（多路召回）
        retrieved = self.rag.hybrid_retrieval(
            query=scoring_item['description'],
            project_context={
                'owner_type': db.get_project(project_id).owner_type,
                'service_type': 'food_delivery',  # 根据业务
                'score_point': scoring_item['keyword']
            },
            top_k=5
        )
        
        contexts = "\n\n---\n\n".join([f"参考方案 {i+1}（质量分{r['quality_score']}）：\n{r['content']}" 
                                     for i, r in enumerate(retrieved)])
        
        # 2. 构建优化策略 Prompt（ABCD）
        prompt = f"""
        【任务】撰写技术方案响应评分项"{scoring_item['name']}"（分值：{scoring_item['weight']}分）
        
        【评分标准要求】
        {scoring_item['description']}
        
        【历史优秀方案参考】
        {contexts}
        
        【优化策略 - 必须严格执行】
        A. 差异化超越：如果标准要求24小时配送，你承诺12小时+2小时应急预备；如果要求95%达标率，你承诺99%并提供惩罚机制
        B. 证据链完整：每个承诺都要有具体数据、流程图描述、检查表支撑，引用过往成功案例（格式："如XX学校2024年配送准时率100%"）
        C. 专家评审友好：使用【评分点响应】格式开头，使用加粗、表格、项目符号，确保专家一眼看到对应关系
        D. 业主语境适配：{'强调"守护师生健康""营养安全""家校共育"，语言有教育情怀和温度' if scoring_item['owner_type'] == 'school' else '强调"规范严谨""合规溯源""应急保障"，语言正式规范，多用政策术语和量化指标'}
        
        【输出格式】
        1. 开头标记：【响应评分项：{scoring_item['name']}】
        2. 方案正文：800-1200字，包含：现状分析→方案设计→保障措施→应急预案
        3. 证据链小节：【本项目优势】列举3条与历史案例的对应优势
        
        直接输出正文，不要解释。
        """
        
        # 3. LLM 生成
        response = self.llm.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000
        )
        
        content = response.choices[0].message.content
        
        # 4. 自动关联业绩案例（从数据库检索）
        linked_cases = self.auto_link_cases(
            project_id=project_id,
            section_topic=scoring_item['name'],
            section_content=content
        )
        
        return {
            'section_title': scoring_item['name'],
            'score_weight': scoring_item['weight'],
            'content': content,
            'source_chunks': [r['id'] for r in retrieved],
            'linked_cases': linked_cases,
            'ai_rewrite_count': 1,
            'generation_timestamp': datetime.now().isoformat()
        }
    
    async def generate_guided_mode(self, project_id: int, scoring_item: dict, 
                                   specialist_input: list) -> dict:
        """
        有内幕定制化模式：严格基于专员录入要点生成
        """
        # 1. 解析专员输入为生成约束
        constraints = []
        brand_requirement = None
        for inp in specialist_input:
            if inp['type'] == 'tag' and inp['key'] == 'brand':
                brand_requirement = inp['value']
                constraints.append(f"必须使用品牌：{inp['value']}")
            elif inp['type'] == 'text':
                constraints.append(f"特殊要求：{inp['content']}")
        
        # 2. RAG 检索（更精准，top_k=3）
        retrieved = self.rag.retrieve_for_guided_mode(specialist_input, {
            'owner_type': db.get_project(project_id).owner_type
        })
        
        contexts = "\n\n".join([r['content'] for r in retrieved]) if retrieved else "无相关历史方案"
        
        # 3. 定制化 Prompt（弱化差异化，强化贴合度）
        prompt = f"""
        【定制化方案生成 - 有内幕关系项目】
        
        【业主特殊要求 - 必须严格遵守】
        {chr(10).join(constraints)}
        
        【评分项要求】
        {scoring_item['description']}
        
        【历史参考（仅作格式参考，内容必须符合上述特殊要求）】
        {contexts}
        
        【生成要求】
        1. 严格体现业主特殊要求（如指定品牌、特定时段、特殊流程）
        2. 证明你完全理解并能满足这些要求（展示过往类似经验）
        3. 语气：{'亲切专业，体现对教育场景的深刻理解' if scoring_item['owner_type'] == 'school' else '严谨规范，体现对行政流程的熟练掌握'}
        4. 不得使用通用模板语言，必须提及业主的具体要求
        
        输出格式同 Auto 模式，但内容必须定制化。
        """
        
        response = self.llm.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,  # 更低温度，更严格遵守约束
            max_tokens=2000
        )
        
        return {
            'section_title': scoring_item['name'],
            'content': response.choices[0].message.content,
            'source_chunks': [r['id'] for r in retrieved],
            'linked_cases': [],  # 有内幕时减少案例堆砌，或手动选择
            'guided_constraints': constraints,  # 记录约束，用于审计
            'ai_rewrite_count': 1
        }
    
    def auto_link_cases(self, project_id: int, section_topic: str, section_content: str) -> list:
        """
        自动关联业绩案例（基于向量相似度匹配案例描述）
        """
        # 从 performance_cases 表检索（Week 1 数据库）
        # 简化：基于项目名称相似度或预算范围匹配
        project = db.get_project(project_id)
        
        cases = db.query("""
            SELECT id, project_name, text_description, contract_amount, owner_unit
            FROM performance_cases
            WHERE owner_type = %s
            AND ABS(contract_amount - %s) / %s < 0.3  -- 预算差异<30%
            ORDER BY case_date DESC
            LIMIT 2
        """, project.owner_type, project.budget_amount, project.budget_amount)
        
        return [{
            'case_id': c['id'],
            'case_name': c['project_name'],
            'relevance': 'auto_matched'  # 后续可加入向量相似度计算
        } for c in cases]
3.3 评分点索引生成器
  
    def generate_scoring_index(project_id: int, sections: list) -> list:
    """
    C策略：生成评分点对应索引表（专家友好）
    """
    index = []
    current_page = 3  # 从第3页开始（封面1页，索引1页）
    
    for section in sections:
        # 预估页数（800字≈1.5页，含图表）
        estimated_pages = max(1, len(section['content']) // 600)
        
        # 提取关键词（用于专家快速定位）
        keywords = extract_keywords(section['content'], top_n=5)
        
        index.append({
            'score_item_name': section['section_title'],
            'score_weight': section['score_weight'],
            'corresponding_section_id': section.get('section_id'),
            'corresponding_section_title': section['section_title'],
            'start_page': current_page,
            'end_page': current_page + estimated_pages - 1,
            'keyword_matches': keywords,
            'is_fully_responded': False  # 待专员确认
        })
        
        current_page += estimated_pages
    
    # 批量插入数据库
    for idx in index:
        db.insert('scoring_indexes', {**idx, 'project_id': project_id})
    
    return index
四、API 接口定义

#POST /api/tech-proposal/{project_id}/initiate
#触发技术标生成（标记内幕/无内幕后调用）
class TechProposalInitiate(BaseModel):
    generation_mode: str  # 'auto' 或 'guided'
    specialist_input: Optional[list] = None  # guided 模式必填，格式见 Week 2 Q17

#Response: {task_id, status: 'generating', estimated_sections: 5}

#GET /api/tech-proposal/{task_id}/progress
#流式返回生成进度（SSE 或轮询）
#Response: {current_section: 2, total_sections: 5, status: 'generating_section_2'}

#GET /api/tech-proposal/{task_id}/content
#获取生成的完整内容（供编辑器加载）
#Response: {sections: [...], scoring_index: [...], generation_mode: 'auto'}

#POST /api/tech-proposal/{task_id}/sections/{section_id}/rewrite
#AI 改写指定段落（编辑器的"AI润色"功能）
class SectionRewrite(BaseModel):
    style: str  # 'more_professional' / 'more_detailed' / 'simplify' / 'adjust_tone'
    custom_instruction: Optional[str] = None  # 自定义指令

#POST /api/tech-proposal/{task_id}/sections/{section_id}/link-case
#手动关联业绩案例（拖拽或选择）
class LinkCase(BaseModel):
    case_id: int
    insert_position: str  # 'beginning' / 'end' / 'current_cursor'

#POST /api/tech-proposal/{task_id}/confirm
#专员确认技术标完成（进入 Week 4）
#校验：所有 scoring_indexes.is_fully_responded = true 才能确认
#Response: {confirmed: true, next_stage: 'pricing', pricing_task_id: null}

#GET /api/tech-proposal/templates
#获取通用模板段落（当 RAG 检索无结果时 fallback）
五、前端界面设计（Web 富文本编辑器）
5.1 技术标编辑工作台（核心界面）

┌─────────────────────────────────────────────────────────────────────┐
│ 项目：XX学校食堂配送（无内幕-极致优化模式）           [保存草稿] [确认完成] │
├─────────────────────────────────────────────────────────────────────┤
│ 左侧导航栏              │ 中间编辑区                    │ 右侧 AI 助手   │
├───────────────────────┼───────────────────────────────┼──────────────┤
│ 评分点索引（C策略）    │                               │              │
│ ├─ 配送方案（20分）    │  【响应评分项：配送方案】      │  选中文字：   │
│ │   第3-5页 [跳转]     │                               │  "12小时配送" │
│ │   关键词：时效/冷链  │  针对学校食堂配送的特殊需求，  │              │
│ ├─ 食品安全（15分）    │  我方承诺实现12小时极速配送    │  [改得更专业] │
│ │   第6-8页 [跳转]     │  服务，并建立2小时应急响应机制 │  [增加数据]   │
│ ├─ ...                │  ...                          │  [调整语气]   │
│                       │                               │              │
│ [生成索引页预览]       │  ┌─────────────────────────┐  │  关联案例：   │
│                       │  │ 【本项目优势】            │  │  XX中学   │
│ 章节状态：             │  │ 1. 类似XX中学项目经验     │  │  XX小学   │
│ ● 配送方案 ✓           │  │ 2. 冷链设备投入保障       │  │  [+添加案例] │
● 食品安全 ✓           │  │ 3. 应急预案完善           │  │              │
│ ○ 人员配置          │  └─────────────────────────┘  │              │
│   （未完全响应）       │                               │              │
├───────────────────────┴───────────────────────────────┴──────────────┤
│ 底部状态栏：总字数 12,580 | 预估页数 18页 | AI生成版本 v2 | 最后保存 2分钟前 │
└─────────────────────────────────────────────────────────────────────┘

5.2 有内幕模式录入界面（生成前）

┌─────────────────────────────────────────────────────────┐
│ 有内幕项目技术要点录入（将严格用于生成定制化方案）          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ 已录入要点：                                            │
│ • [品牌] 必须使用：双汇肉类产品                          │
│ • [时段] 避开上下学高峰（9:30-11:00, 14:00-16:00）      │
│ • [特殊] 需提供每周营养成分表给家长公示                  │
│                                                         │
│ [添加要点]                                              │
│ ├─ 标签式： [选择类型▼] [输入值]                        │
│ └─ 描述式： [文本输入框...]                             │
│                                                         │
│ [开始定制化生成]  ← 基于以上要点 + 历史知识库生成         │
└─────────────────────────────────────────────────────────┘

六、关键业务校验规则
模式锁定：generation_mode 在初始化后不可更改（防止中途切换导致内容混乱），如需更改需新建任务。
检索阈值：RAG 检索相似度 < 0.75 时，系统提示"缺少高质量历史参考，建议人工重点审核"，并在生成内容中标记【通用模板】警告。
索引强制：确认技术标前，必须生成 scoring_indexes 记录，且所有 is_fully_responded 为 true（前端强制打钩确认）。
版本控制：每次 AI 改写（rewrite）增加 editor_version，保留最近 5 个版本历史（可回溯）。
案例上限：单个章节关联业绩案例不得超过 2 个，超过时系统警告"案例堆砌可能影响专家评审"。
七、交付标准（Week 3 验收 checklist）
[ ] 无内幕项目：上传招标文件后，自动生成含 3+ 章节的技术标，包含【评分点响应】标记和证据链小节
[ ] 有内幕项目：录入"必须使用A品牌"后，生成内容中必须出现A品牌及相关供应链保障描述
[ ] Web 编辑器：可选中段落点击"改得更专业"，AI 重写后内容更新且版本号+1
[ ] 评分点索引：自动生成并显示页码，点击导航跳转对应章节
[ ] 业绩案例：自动关联历史案例，显示📎图标，点击可查看案例详情
[ ] 确认机制：所有章节标记"完全响应"后，【确认完成】按钮可用，点击后进入 Week 4 定价环节

Week 3 核心是生成质量与人机协同体验。务必确保：
RAG 检索的 pgvector 索引已正确创建（Week 1 基础上）
Prompt 工程严格体现 ABCD 策略（特别是差异化超越和专家友好索引）
编辑器使用成熟库（如 TipTap、Slate.js 或 Quill），避免从零开发富文本
与 Week 2 的 scoring_items 和 Week 1 的 knowledge_chunks 表正确关联外键