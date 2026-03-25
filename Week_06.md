Week 6 开发文档：复盘与知识进化系统（RKE - Review & Knowledge Evolution）
文档元信息
开发周期：Week 6（5个工作日）
依赖前提：Week 1-5 已完成（特别是Week 5的废弃草稿库、形式审查记录）
核心业务目标：实现投标后复盘→知识库自进化→二次投标智能提醒的闭环
关键价值：让系统从"11份文件"进化为"持续学习的投标大脑"
一、业务逻辑架构（必读）
1.1 复盘与进化 Workflow（闭环核心）

[投标结束] ← 中标/未中标/废标
    ↓
[结果录入] ← 人工录入中标价、竞争对手、是否中标
    ↓
[自动复盘分析]
    ├─ 如废标：投标文件 vs 废标公告（如有）→ 自动提取差异点
    ├─ 如未中标：投标文件 vs 中标公告 → 分析丢分点（价格/技术）
    └─ 如中标：投标文件 vs 招标文件评分标准 → 提取中标DNA（高分段落）
    ↓
[人工复盘确认] ← 标书专员/老板确认分析结果，补充人工洞察
    ↓
[知识库进化]
    ├─ 中标DNA入库 → 知识库加权（quality_score提升）
    ├─ 废标陷阱入库 → 风险库更新（formal_review_items模板更新）
    ├─ 废弃草稿复活 → 如项目重招，自动提醒历史原因
    └─ 冷门知识清理 → usage_count=0的知识块标记待淘汰
    ↓
[二次投标触发]
    └─ 检测到同一项目重招（名称相似+业主相同+时间接近）
       → 自动推送提醒："历史废标原因：XX，请特别注意"
       → 自动推荐历史技术标段落（可复用部分）

1.2 关键业务规则（硬性约束）
规则1：复盘数据来源
自动提取：爬取公共资源交易中心的中标/废标公告（如可获取）
人工录入：必须录入字段：
中标状态：win / lose / disqualified（废标）
中标价（如公开）：用于价格库积累
中标单位（如公开）：用于竞争对手库积累
废标原因（如废标）：关联到 formal_review_items
规则2：中标DNA提取逻辑（学习什么有效）
对比中标投标文件 vs 原招标文件：
技术标高分段落：哪些章节的表述被认可（无法直接获取分数，但可通过"中标且技术分未投诉"推断）
报价策略：中标价 vs 预算价的下浮率（进入 price_history 库）
资质组合：中标时使用的资质清单（进入标准参考）
规则3：废标根因分析（避免重复错误）
自动关联：对比Week 5的 formal_review_items，定位具体哪项检查失败
责任追溯：如果废标原因是形式审查项（如签字漏页），而该检查项在Week 5被专员标记为【修正/删除】（即人工说没问题），则标记为"人工误判"，用于训练专员
复盘库分类：
fatal_formal：形式审查致命错误（签字、盖章、密封）
fatal_qualification：资质不符（证书过期、等级不足）
fatal_price：报价错误（超限价、计算错误）
tech_deficiency：技术标不足（评分低）
price_uncompetitive：价格过高（未中标但无错误）
规则4：知识库进化算法
加权机制：中标项目的技术标段落，quality_score +20，权重提升
淘汰机制：usage_count=0 且 created_at < 3个月前 的知识块，标记is_deprecated=true，不再参与RAG检索
复活机制：废弃草稿（Week 5）中的技术标段落，如项目重招，可一键恢复为"初稿"，并提示"基于历史版本，请根据新招标文件调整"
规则5：二次投标智能提醒
检测规则：新上传的招标文件 vs 历史项目：
业主名称相似度 > 90%
项目名称相似度 > 70%（如"2025年食堂配送" vs "2026年食堂配送"）
时间差 < 12个月
→ 判定为"疑似重招项目"，自动关联历史复盘记录

二、数据库表设计（SQL）

    -- 投标结果记录表（投标后录入）
    CREATE TABLE bid_outcomes (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    
    -- 基础结果
    outcome_status VARCHAR(20) CHECK (outcome_status IN ('win', 'lose', 'disqualified', 'abandoned', 'withdrawn')),
    outcome_date DATE,  -- 中标公告日期/废标公告日期
    
    -- 财务数据（用于价格库积累）
    final_bid_price DECIMAL(15,2),  -- 我们的最终报价
    winning_price DECIMAL(15,2),    -- 中标价（公开数据）
    winning_unit VARCHAR(255),      -- 中标单位（竞争对手分析）
    our_price_rank INTEGER,         -- 我们的价格排名（如：第2低价）
    
    -- 废标专项（如 outcome_status='disqualified'）
    disqualification_reason TEXT,   -- 废标原因描述（来自公告）
    disqualification_type VARCHAR(50), -- fatal_formal / fatal_qualification / fatal_price / tech_deficiency
    related_review_item_id INTEGER REFERENCES formal_review_items(id), -- 关联到Week 5的检查项（如形式审查失败）
    is_manual_error BOOLEAN,        -- 是否人工误判（如专员说签字没问题实际有问题）
    
    -- 复盘分析（JSON存储详细对比）
    review_analysis JSONB,  -- {
                            --   "price_analysis": {"our_discount": 0.05, "winner_discount": 0.08, "gap": 0.03},
                            --   "tech_analysis": {"strengths": ["方案详实"], "weaknesses": ["案例不足"]},
                            --   "formal_failure_point": "authorization_signature_page5"
                            -- }
    
    -- 复盘确认
    reviewed_by INTEGER REFERENCES users(id),
    reviewed_at TIMESTAMP,
    review_notes TEXT,      -- 人工复盘总结（如："下次需注意XX"）
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 中标DNA提取表（高分段落标记）
    CREATE TABLE winning_dna (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    source_chunk_id INTEGER REFERENCES knowledge_chunks(id),  -- 关联到知识库
    
    -- DNA特征
    dna_type VARCHAR(50) CHECK (dna_type IN ('high_score_response', 'winning_price_strategy', 'effective_case_usage', 'format_excellence')),
    score_contribution INTEGER CHECK (score_contribution BETWEEN 1 AND 10),  -- 预估贡献分（人工评估或推断）
    
    -- 上下文（用于后续复用）
    scoring_item_matched VARCHAR(255),  -- 对应哪个评分项
    owner_type VARCHAR(50),             -- 适用业主类型
    project_scale VARCHAR(50),          -- 适用规模
    
    -- 复用统计
    reused_in_projects JSONB,  -- [123, 456, 789] 被哪些后续项目复用
    reuse_success_rate DECIMAL(5,2),  -- 复用后的中标率
    
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_by INTEGER REFERENCES users(id)  -- 人工确认有效
    );

     -- 废标陷阱库（风险知识积累）
    CREATE TABLE disqualification_traps (
    id SERIAL PRIMARY KEY,
    trap_code VARCHAR(50) UNIQUE,  -- 如：AUTH_DATE_INVALID, SEAL_MISSING_COVER
    trap_category VARCHAR(50) CHECK (trap_category IN ('signature', 'seal', 'qualification', 'price', 'format', 'timing')),
    trap_title VARCHAR(255),     -- 如："授权书日期早于营业执照日期"
    trap_description TEXT,         -- 详细描述和后果
    detection_method TEXT,         -- 系统如何检测（正则/关键词/OCR）
    
    -- 关联数据
    first_occurrence_project_id INTEGER REFERENCES projects(id),  -- 首次出现
    occurrence_count INTEGER DEFAULT 1,  -- 发生次数（统计）
    
    -- 预防措施（用于Week 5形式审查自动生成检查项）
    prevention_checklist_item TEXT,  -- 对应的检查项模板
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 废弃草稿复活记录（Week 5废弃 → Week 6复活）
    CREATE TABLE draft_revivals (
    id SERIAL PRIMARY KEY,
    abandoned_draft_id INTEGER REFERENCES abandoned_drafts(id),
    new_project_id INTEGER REFERENCES projects(id),  -- 复活到的新项目
    
    revival_type VARCHAR(50) CHECK (revival_type IN ('rebid_same_project', 'similar_project_reference')),
    revived_content JSONB,  -- 复活的内容清单（如：["tech_proposal_section_1", "pricing_strategy"]）
    adaptation_notes TEXT,  -- 适配新项目的调整建议（AI生成）
    
    revived_by INTEGER REFERENCES users(id),
    revived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_successful BOOLEAN  -- 最终是否中标（用于评估复活效果）
    );

    -- 知识库进化日志（追踪知识块的生命周期）
    CREATE TABLE knowledge_evolution_logs (
    id SERIAL PRIMARY KEY,
    chunk_id INTEGER REFERENCES knowledge_chunks(id),
    action_type VARCHAR(50) CHECK (action_type IN ('created', 'weighted', 'deprecated', 'reused', 'confirmed_win', 'confirmed_lose')),
    project_id INTEGER REFERENCES projects(id),  -- 关联项目
    
    old_quality_score INTEGER,
    new_quality_score INTEGER,
    reason TEXT,  -- 如："中标项目X贡献，+20分"
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

三、核心算法逻辑（Python 伪代码）

3.1 自动复盘分析引擎

    class BidReviewEngine:
    def __init__(self, project_id: int):
        self.project_id = project_id
        self.project = db.get_project(project_id)
        self.outcome = db.get_bid_outcome(project_id)
        
    def auto_analyze(self) -> dict:
        """
        根据投标结果自动触发不同分析逻辑
        """
        if self.outcome.outcome_status == 'disqualified':
            return self._analyze_disqualification()
        elif self.outcome.outcome_status == 'lose':
            return self._analyze_loss()
        elif self.outcome.outcome_status == 'win':
            return self._analyze_win()
    
    def _analyze_disqualification(self) -> dict:
        """
        废标分析：定位具体失败点
        """
        analysis = {
            'type': 'disqualification',
            'detected_trap': None,
            'is_manual_error': False,
            'suggestions': []
        }
        
        # 1. 解析废标公告（如有文本）
        disqual_notice = self.outcome.disqualification_reason
        
        # 2. 对比Week 5形式审查记录
        week5_reviews = db.query("""
            SELECT * FROM formal_review_items 
            WHERE project_id = %s AND risk_level = 'fatal'
        """, self.project_id)
        
        # 3. 匹配废标原因与审查项
        for review in week5_reviews:
            if review.check_description in disqual_notice or \
               self._fuzzy_match_trap(review.check_title, disqual_notice):
                analysis['detected_trap'] = review.check_category
                analysis['related_review_item'] = review.id
                
                # 关键：检查Week 5时专员是否误判
                if review.specialist_status in ['confirmed', 'corrected'] and review.system_status == 'failed':
                    # 专员说没问题但系统说有问题 → 专员对了？还是废标原因不同？
                    pass
                elif review.specialist_status == 'deleted':
                    # 专员删除了系统警告，结果真的废标了 → 人工误判！
                    analysis['is_manual_error'] = True
                    analysis['suggestions'].append("形式审查阶段删除了系统警告项，导致废标。建议：信任系统检查，人工修正需提供强证据")
                
                break
        
        # 4. 更新/插入废标陷阱库
        if analysis['detected_trap']:
            self._update_trap_library(analysis)
        
        return analysis
    
    def _analyze_win(self) -> dict:
        """
        中标分析：提取中标DNA
        """
        analysis = {
            'type': 'win',
            'dna_extracted': [],
            'price_strategy': None
        }
        
        # 1. 价格策略DNA
        pricing = db.get_pricing_decision(self.project_id)
        if pricing:
            discount_rate = (pricing.boss_final_price - pricing.cost_base) / pricing.budget_limit
            analysis['price_strategy'] = {
                'discount_rate': discount_rate,
                'strategy_type': 'aggressive' if discount_rate < 0.05 else 'balanced',
                'expected_profit_margin': (pricing.boss_final_price - pricing.cost_base) / pricing.boss_final_price
            }
            
            # 进入价格历史库
            db.insert('price_history', {
                'project_type': self.project.project_type,
                'region': self.project.region,
                'budget_amount': pricing.budget_limit,
                'our_cost': pricing.cost_base,
                'our_bid_price': pricing.boss_final_price,
                'winning_price': pricing.boss_final_price,  # 我们中了
                'discount_rate': discount_rate,
                'is_our_win': True
            })
        
        # 2. 技术标高分DNA提取
        tech_task = db.get_tech_proposal_task(self.project_id)
        if tech_task:
            sections = json.loads(tech_task.final_content or tech_task.generated_content)
            
            for section in sections:
                # 标记为高分DNA（中标了，默认所有章节都有效）
                # 后续根据业主反馈或专家评分细化
                chunk_ids = section.get('source_chunks', [])
                
                for chunk_id in chunk_ids:
                    # 提升知识块权重
                    db.update('knowledge_chunks', {
                        'id': chunk_id,
                        'quality_score': sql.literal_column('quality_score') + 20,
                        'usage_count': sql.literal_column('usage_count') + 1
                    })
                    
                    # 记录中标DNA
                    dna_id = db.insert('winning_dna', {
                        'project_id': self.project_id,
                        'source_chunk_id': chunk_id,
                        'dna_type': 'high_score_response',
                        'scoring_item_matched': section['section_title'],
                        'owner_type': self.project.owner_type
                    })
                    
                    analysis['dna_extracted'].append(dna_id)
        
        # 3. 记录知识进化
        for dna in analysis['dna_extracted']:
            db.insert('knowledge_evolution_logs', {
                'chunk_id': dna['source_chunk_id'],
                'action_type': 'confirmed_win',
                'project_id': self.project_id,
                'reason': f'中标项目贡献，+20质量分'
            })
        
        return analysis
    
    def detect_similar_rebid(self, new_project_id: int) -> dict:
        """
        检测新项目是否为历史项目的重招
        """
        new_project = db.get_project(new_project_id)
        
        # 相似度计算
        similar_projects = db.query("""
            SELECT p.*, bo.outcome_status, bo.disqualification_type,
                   similarity(p.owner_unit, %s) as owner_sim,
                   similarity(p.project_name, %s) as name_sim
            FROM projects p
            LEFT JOIN bid_outcomes bo ON bo.project_id = p.id
            WHERE p.id != %s
            AND p.bid_open_date < %s
            AND similarity(p.owner_unit, %s) > 0.9
            ORDER BY p.bid_open_date DESC
        """, new_project.owner_unit, new_project.project_name, 
             new_project_id, new_project.created_at, new_project.owner_unit)
        
        if similar_projects and similar_projects[0]['name_sim'] > 0.7:
            hist = similar_projects[0]
            
            alert = {
                'is_rebid': True,
                'historical_project_id': hist['id'],
                'similarity_score': (hist['owner_sim'] + hist['name_sim']) / 2,
                'historical_outcome': hist['outcome_status'],
                'warnings': []
            }
            
            # 如果历史废标，提取原因
            if hist['outcome_status'] == 'disqualified':
                trap = db.get_disqualification_trap(hist['id'])
                alert['warnings'].append(f" 历史废标原因：{trap['trap_title'] if trap else '未知'}，请务必检查")
            
            # 如果历史中标，推荐DNA
            if hist['outcome_status'] == 'win':
                dnas = db.query("SELECT * FROM winning_dna WHERE project_id = %s", hist['id'])
                alert['recommended_dna'] = [d['id'] for d in dnas]
                alert['warnings'].append(f" 历史中标项目，推荐复用技术方案DNA：{len(dnas)}个高分段落")
            
            return alert
        
        return {'is_rebid': False}

3.2 废弃草稿复活引擎

    class DraftRevivalEngine:
    def revive_for_rebid(self, abandoned_draft_id: int, new_project_id: int) -> dict:
        """
        将废弃草稿复活到新项目
        """
        draft = db.get_abandoned_draft(abandoned_draft_id)
        new_project = db.get_project(new_project_id)
        
        revival_content = []
        
        # 1. 技术标复活
        if draft['tech_proposal_path'] and os.path.exists(draft['tech_proposal_path']):
            # 解析旧技术标内容
            old_sections = parse_docx_sections(draft['tech_proposal_path'])
            
            # AI分析：哪些章节可复用（通用性 vs 特异性）
            for section in old_sections:
                reusability_score = self._calculate_reusability(section, new_project)
                
                if reusability_score > 0.7:
                    # 直接导入知识库并关联新项目
                    new_chunk_id = self._import_to_knowledge_base(section, new_project_id, source='revived_draft')
                    revival_content.append({
                        'type': 'tech_section',
                        'title': section['title'],
                        'reusability': reusability_score,
                        'new_chunk_id': new_chunk_id,
                        'adaptation_hint': '需更新具体数据（如配送量、时间）'
                    })
        
        # 2. 定价策略复活（仅参考）
        if draft['pricing_decision_id']:
            old_pricing = db.get_pricing_decision(draft['pricing_decision_id'])
            revival_content.append({
                'type': 'pricing_strategy',
                'old_price': old_pricing['boss_final_price'],
                'hint': f"历史报价{old_pricing['boss_final_price']}万，可作为新项目定价参考"
            })
        
        # 记录复活
        revival_id = db.insert('draft_revivals', {
            'abandoned_draft_id': abandoned_draft_id,
            'new_project_id': new_project_id,
            'revival_type': 'rebid_same_project',
            'revived_content': json.dumps(revival_content),
            'adaptation_notes': '请根据新招标文件调整具体参数'
        })
        
        return {
            'revival_id': revival_id,
            'revived_items': revival_content,
            'suggestion': f"已复活{len(revival_content)}项历史内容，请在技术标编辑器中查看'复活段落'标签"
        }
    
    def _calculate_reusability(self, section: dict, new_project: dict) -> float:
        """
        计算旧章节对新项目的可复用性（0-1）
        """
        score = 0.5  # 基础分
        
        # 如果都是学校类型，+0.3
        if section.get('owner_type') == new_project['owner_type']:
            score += 0.3
        
        # 如果是通用流程章节（如食品安全管理），+0.2
        if any(keyword in section['title'] for keyword in ['食品安全', '应急', '管理流程']):
            score += 0.2
        
        return min(score, 1.0)

3.3 知识库自进化（清理与加权）

    class KnowledgeEvolution:
    def evolve(self):
        """
        定期执行的知识库进化任务（可设为每周日凌晨运行）
        """
        # 1. 热门知识加权（中标DNA）
        winning_chunks = db.query("""
            SELECT chunk_id, COUNT(*) as win_count
            FROM winning_dna
            WHERE created_at > NOW() - INTERVAL '3 months'
            GROUP BY chunk_id
        """)
        
        for wc in winning_chunks:
            db.update('knowledge_chunks', {
                'id': wc['chunk_id'],
                'quality_score': sql.literal_column('quality_score') + (wc['win_count'] * 10)
            })
            
            db.insert('knowledge_evolution_logs', {
                'chunk_id': wc['chunk_id'],
                'action_type': 'weighted',
                'new_quality_score': db.query("SELECT quality_score FROM knowledge_chunks WHERE id=%s", wc['chunk_id'])[0]['quality_score'],
                'reason': f'近3个月中标贡献{wc["win_count"]}次'
            })
        
        # 2. 冷门知识标记淘汰
        cold_chunks = db.query("""
            SELECT id, usage_count, created_at, quality_score
            FROM knowledge_chunks
            WHERE usage_count = 0 
            AND created_at < NOW() - INTERVAL '3 months'
            AND quality_score < 50
        """)
        
        for cc in cold_chunks:
            db.update('knowledge_chunks', {
                'id': cc['id'],
                'is_deprecated': True
            })
            
            db.insert('knowledge_evolution_logs', {
                'chunk_id': cc['id'],
                'action_type': 'deprecated',
                'reason': '3个月零使用且质量分<50，标记淘汰'
            })
        
        # 3. 废标陷阱库更新（基于Week 5数据）
        new_traps = db.query("""
            SELECT disqualification_type, disqualification_reason, COUNT(*) as cnt
            FROM bid_outcomes
            WHERE outcome_status = 'disqualified'
            AND created_at > NOW() - INTERVAL '1 month'
            GROUP BY disqualification_type, disqualification_reason
            HAVING COUNT(*) >= 2  -- 出现2次以上的才入库
        """)
        
        for trap in new_traps:
            # 插入或更新陷阱库
            db.upsert('disqualification_traps', {
                'trap_code': self._generate_trap_code(trap['disqualification_reason']),
                'trap_category': trap['disqualification_type'],
                'trap_title': trap['disqualification_reason'][:50],
                'occurrence_count': trap['cnt']
            })

四、API 接口定义
#POST /api/projects/{project_id}/outcomes/record
#投标结束后录入结果（触发复盘分析）
class BidOutcomeRecord(BaseModel):
    outcome_status: str  # win/lose/disqualified
    outcome_date: date
    final_bid_price: float
    winning_price: Optional[float] = None
    winning_unit: Optional[str] = None
    disqualification_reason: Optional[str] = None
    disqualification_notice_file: Optional[str] = None  # 上传废标公告PDF

#GET /api/projects/{project_id}/review-analysis
#获取自动复盘分析结果
#Response: {
#'type': 'disqualification'/'win'/'lose',
#'analysis': {...},
#'suggested_actions': ['更新形式审查清单', '提取中标DNA']
#}

#POST /api/projects/{project_id}/review-analysis/confirm
#人工确认复盘结果，确认后触发知识库更新
class ReviewConfirm(BaseModel):
    confirmed_analysis: dict  # 确认或修正自动分析
    manual_notes: str  # 人工复盘总结
    extract_dna: bool = True  # 是否提取DNA（中标时）
    update_traps: bool = True  # 是否更新陷阱库（废标时）

#GET /api/projects/{new_project_id}/rebid-alert
#检测是否为重招项目（上传招标文件后自动调用）
#Response: {
#is_rebid': true,
#historical_project_id': 123,
#'historical_outcome': 'disqualified',
#'alert_level': 'high',  # high=废标历史, medium=未中标, low=中标历史
#'warnings': ['历史废标原因：签字漏页', '推荐复用DNA段落ID: 456, 789'],
#'revivable_drafts': [{draft_id: 111, revival_suggestion: '技术标可复用80%'}]
#}

#POST /api/revivals/{abandoned_draft_id}/revive-to/{new_project_id}
#执行废弃草稿复活
#Response: {
#'revival_id': 999,
#'revived_content': [...],
#'imported_to_knowledge_base': [chunk_id1, chunk_id2]
#}

#GET /api/knowledge-base/evolution-report
#知识库进化报告（看板数据）
#Response: {
#'total_chunks': 1500,
#'deprecated_this_month': 45,
#'weighted_by_wins': 120,
#'new_traps_added': 3,
#'avg_quality_score_trend': 'up'  # up/down/stable
#}
五、前端界面设计
5.1 复盘录入界面（投标结束后）

┌─────────────────────────────────────────────────────────────┐
│ 项目复盘：XX学校食堂配送（已结束）                              │
├─────────────────────────────────────────────────────────────┤
│ 结果录入：                                                   │
│ ○ 中标  ○ 未中标  ● 废标                                    │
│                                                              │
│ 如废标：                                                     │
│ 废标原因（从公告复制）：______________________________        │
│ 上传废标公告PDF： [选择文件]                                 │
│                                                              │
│ [开始自动分析]                                               │
├─────────────────────────────────────────────────────────────┤
│ 自动分析结果（系统生成，可人工修正）：                          │
│                                                              │
│ 🔴 检测到的致命错误：                                         │
│ 类型：形式审查 - 签字盖章                                     │
│ 详情：Week 5形式审查时系统提示"第5页授权书缺少签字"，          │
│      专员标记为【修正："实际有签字"】，但废标公告明确          │
│      指出"授权书法定代表人签字缺失"。                         │
│ 判定：人工误判（系统正确，专员错误删除警告）                    │
│                                                              │
│ 建议措施：                                                    │
│ 1. 将"授权书签字"检查项升级为强制不可删除项                      │
│ 2. 对专员进行提醒：下次形式审查信任系统判断                      │
│                                                              │
│ [确认分析结果并更新知识库]  [修正分析结果]                      │
└─────────────────────────────────────────────────────────────┘

5.2 废弃草稿复活界面（重招项目触发）
┌─────────────────────────────────────────────────────────────┐
│ 🔔 智能提醒：检测到重招项目                                    │
│                                                              │
│ 新项目：XX学校2026年食堂配送                                  │
│ 历史项目：XX学校2025年食堂配送（6个月前）                       │
│ 历史结果：❌ 废标（形式审查：签字缺失）                         │
│                                                              │
│ 可复活资源：                                                  │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 技术标草稿（2025-10-15生成）                             │ │
│ │ 状态：废弃但未使用                                        │ │
│ │ 可复用性：85%（仅需更新配送量、时间参数）                   │ │
│ │ [查看历史版本] [一键复活到当前项目]                        │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ 历史陷阱提醒：                                                │
│ ⚠️ 上次废标原因：授权书第5页缺少法定代表人签字                 │
│ ✅ 本次形式审查已自动增加不可删除的强制检查项                  │
│                                                              │
│ 推荐策略：                                                    │
│ • 价格策略：上次报价142万（预算150万），建议本次参考           │
│ • 技术方案：上次"冷链配送方案"章节评分较高，建议保留            │
└─────────────────────────────────────────────────────────────┘

六、关键业务校验规则
复盘触发强制：项目状态为completed（Week 5生成最终标书）后，必须录入bid_outcomes才能归档。超过7天未录入，系统每日提醒。
人工误判标记：如果formal_review_items中specialist_status='deleted'且最终bid_outcomes.outcome_status='disqualified'且原因匹配，自动标记is_manual_error=true，用于专员培训。
DNA提取确认：中标DNA默认提取，但需老板/专员在复盘界面确认extract_dna=true才正式加权入库（防止偶然中标）。
复活限制：废弃草稿只能在abandoned_at后12个月内复活，超过期限自动清理（物理删除或归档冷存储）。
七、交付标准（验收 checklist）
[ ] 上传废标公告PDF，系统自动关联到Week 5的formal_review_items，定位失败点
[ ] 中标项目的技术标段落自动+20质量分，并在winning_dna表生成记录
[ ] 上传与历史项目相似的招标文件，系统提示"检测到重招"，显示历史废标原因
[ ] 点击"一键复活"，历史技术标段落导入新知识库，并在编辑器显示"复活段落"标签
[ ] 运行知识库进化任务，usage_count=0的冷门知识被标记is_deprecated=true
[ ] 废标陷阱库自动统计：近1个月出现2次以上的废标原因自动生成新的陷阱检查项模板

Week 6 是系统的自我进化能力，核心是闭环学习。务必确保：
bid_outcomes表与前面所有表（Week 1-5）的关联正确（外键关系）
复盘分析的结果要能反馈优化Week 3的知识库和Week 5的形式审查清单
复活功能要处理文件路径有效性（废弃草稿文件可能已移动或删除，需容错）
至此，Week 1-6完整覆盖了上传→解析→初筛→生成→定价→审查→输出→复盘→进化的全生命周期。