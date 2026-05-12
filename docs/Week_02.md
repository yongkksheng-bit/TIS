Week 2 开发文档：初筛报告生成引擎与智能评估系统（SIE - Screening & Intelligence Engine）
文档元信息
开发周期：Week 2（5个工作日）
依赖前提：Week 1 已完成（数据库搭建、PDF/Word解析、OCR扫描件识别、标准资质库 standard_certifications 初始化）
核心业务目标：实现招标文件上传→解析确认→初筛报告生成→专员审批/老板监督→进入Week 3的完整闭环
关键区分：有内幕/无内幕项目的初筛逻辑差异、审批权限（选项A：专员独立审批+老板事后推翻）
一、业务逻辑架构（必读）
1.1 初筛报告 Workflow（Week 2 核心流程）
[Week 1 文件解析完成]
    ↓
[并排确认界面] ← 标书专员确认解析结果（评分标准、资质要求、时间节点）
    ↓
[初筛报告生成] ← 系统自动计算：
    ├─ 资质匹配度：投标文件OCR结果 vs 招标文件要求（精确匹配算法）
    ├─ 时间充裕度：距离开标天数（>30天充裕，<7天紧急/红色警告）
    ├─ 业主画像匹配：历史合作次数 → 关系指数（0=无，>0=有）
    ├─ 盈亏测算：基于历史数据或预算比例的成本估算
    └─ 综合中标概率：资质×时间×关系×竞争烈度（启发式算法）
    ↓
[初筛报告展示] ← 推送给专员和老板
    ↓
[审批决策（选项A模式）]
    ├─ 标书专员操作：点击【worthy】或【unworthy】（立即生效）
    │   ├─ worthy → 项目状态变为"approved_by_specialist"，进入Week 3
    │   └─ unworthy → 项目移入"放弃库"，通知老板
    └─ 老板监督（事后）：
        ├─ 查看"今日专员已审批项目"列表
        ├─ 可【推翻】：worthy→unworthy（强制终止）或 unworthy→worthy（复活）
        └─ 推翻操作记录审计日志，项目冻结或激活
    ↓
[worthy 分支] ← 标记内幕/无内幕 → 进入Week 3技术标生成

[Week 1 文件解析完成]
    ↓
[并排确认界面] ← 标书专员确认解析结果（评分标准、资质要求、时间节点）
    ↓
[初筛报告生成] ← 系统自动计算：
    ├─ 资质匹配度：投标文件OCR结果 vs 招标文件要求（精确匹配算法）
    ├─ 时间充裕度：距离开标天数（>30天充裕，<7天紧急/红色警告）
    ├─ 业主画像匹配：历史合作次数 → 关系指数（0=无，>0=有）
    ├─ 盈亏测算：基于历史数据或预算比例的成本估算
    └─ 综合中标概率：资质×时间×关系×竞争烈度（启发式算法）
    ↓
[初筛报告展示] ← 推送给专员和老板
    ↓
[审批决策（选项A模式）]
    ├─ 标书专员操作：点击【worthy】或【unworthy】（立即生效）
    │   ├─ worthy → 项目状态变为"approved_by_specialist"，进入Week 3
    │   └─ unworthy → 项目移入"放弃库"，通知老板
    └─ 老板监督（事后）：
        ├─ 查看"今日专员已审批项目"列表
        ├─ 可【推翻】：worthy→unworthy（强制终止）或 unworthy→worthy（复活）
        └─ 推翻操作记录审计日志，项目冻结或激活
    ↓
[worthy 分支] ← 标记内幕/无内幕 → 进入Week 3技术标生成

二、数据库表设计（新增Week 2表，衔接Week 1
业主画像库（Week 2初始化，基于11份历史文件录入）

    CREATE TABLE owner_profiles (
    id SERIAL PRIMARY KEY,
    owner_name VARCHAR(255) NOT NULL,          -- 单位全称（标准化，去重）
    owner_type VARCHAR(50) CHECK (owner_type IN ('school', 'government', 'hospital', 'enterprise')),
    region VARCHAR(100),                       -- 所在地区（用于地域匹配）
    
    -- 关系数据
    cooperation_count INTEGER DEFAULT 0,       -- 历史合作次数
    last_cooperation_date DATE,                -- 上次合作时间
    relationship_level VARCHAR(20) CHECK (relationship_level IN ('none', 'weak', 'medium', 'strong')),
    
    -- 偏好数据（用于Week 3语境适配）
    avg_winning_discount DECIMAL(5,2),         -- 历史平均下浮率（如0.15表示15%）
    preferred_styles JSONB,                    -- {"tech_detail_level": "high", "price_sensitivity": "medium"}
    common_requirements JSONB,                 -- ["偏爱本地食材", "要求HACCP", "严格时效"]
    blacklist_flags JSONB,                     -- ["经常拖欠", "验收苛刻"]（预警用）
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(owner_name, region)                 -- 同一地区同一单位去重
    );

    -- 初筛报告表（核心决策依据）
    CREATE TABLE bid_evaluation_reports (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    report_version INTEGER DEFAULT 1,          -- 版本控制（重新解析时递增）
    
    -- 资质匹配评估（衔接Week 1的OCR和标准库）
    qualification_match_score INTEGER CHECK (qualification_match_score BETWEEN 0 AND 100),
    missing_mandatory_certs JSONB,             -- 致命缺失：[{cert_code, cert_name, reason}]
    missing_optional_certs JSONB,              -- 加分缺失：[cert_code]
    matched_certs_detail JSONB,                -- 详细匹配结果（用于展示）
    
    -- 时间与进度评估
    days_until_bid_open INTEGER,               -- 距离开标天数（可负，表示已过期）
    time_urgency_level VARCHAR(20) CHECK (time_urgency_level IN ('expired', 'urgent', 'tight', 'normal', 'relaxed')),
    is_time_sufficient BOOLEAN,                -- 是否充裕（用于快速判断）
    
    -- 业主与竞争评估
    owner_profile_id INTEGER REFERENCES owner_profiles(id),
    relationship_index INTEGER CHECK (relationship_index BETWEEN 0 AND 100), -- 0或基于合作次数计算
    is_new_owner BOOLEAN,                      -- 是否首次接触（关系指数=0）
    
    -- 财务估算（Week 4详细定价的前置）
    estimated_cost DECIMAL(15,2),              -- 预估成本（基于历史或预算比例）
    suggested_price_range_low DECIMAL(15,2), -- 建议报价下限（成本×1.02）
    suggested_price_range_high DECIMAL(15,2),  -- 建议报价上限（成本×1.15）
    cost_estimate_confidence VARCHAR(20),      -- high/medium/low（历史数据充足度）
    
    -- 综合评估
    overall_win_probability DECIMAL(5,4),      -- 综合中标概率0-1（启发式算法）
    risk_level VARCHAR(20) CHECK (risk_level IN ('high', 'medium', 'low')),
    fatal_risks JSONB,                         -- 致命风险列表（阻止审批worthy）
    warning_risks JSONB,                       -- 警告风险列表（提示但不阻止）
    
    -- 决策建议（系统算法生成）
    recommendation VARCHAR(20) CHECK (recommendation IN ('worth_bidding', 'abandon', 'conditional')),
    recommendation_reason TEXT,                -- 建议理由文本
    
    -- 生成元数据
    generated_by VARCHAR(50) DEFAULT 'system',
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 审批状态（选项A模式）
    confirmed_by_specialist BOOLEAN DEFAULT FALSE,
    specialist_decision VARCHAR(20),         -- worthy/unworthy
    specialist_notes TEXT,                     -- 专员审批备注（如放弃原因）
    confirmed_at TIMESTAMP,
    
    overridden_by_boss BOOLEAN DEFAULT FALSE,  -- 是否被老板推翻
    boss_override_reason TEXT,                 -- 推翻理由
    
    UNIQUE(project_id, report_version)
    );

    审批日志审计表（记录所有审批操作，用于责任追溯）
    CREATE TABLE approval_logs (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    
    action_type VARCHAR(50) CHECK (action_type IN (
        'specialist_worthy', 'specialist_unworthy',
        'boss_override_revive', 'boss_override_terminate',
        'boss_confirm_specialist'  -- 老板确认专员决策（不推翻）
    )),
    
    actor_role VARCHAR(50),                    -- specialist/boss
    actor_id INTEGER REFERENCES users(id),
    reason_text TEXT,                          -- 操作理由
    
    original_status VARCHAR(50),               -- 变更前状态
    new_status VARCHAR(50),                   -- 变更后状态
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    废弃项目库（放弃库，支持复活）
    CREATE TABLE discarded_projects (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    original_evaluation_report_id INTEGER REFERENCES bid_evaluation_reports(id),
    
    discarded_by VARCHAR(50),                -- specialist/boss
    discard_reason TEXT,                       -- 放弃原因（资质不符/时间不够/利润不足等）
    discard_stage VARCHAR(50),                -- 在哪个阶段放弃（evaluation/tech_generation等）
    
    -- 复活机制
    can_be_revived BOOLEAN DEFAULT TRUE,
    revived_at TIMESTAMP,
    revived_by INTEGER REFERENCES users(id),
    revived_to_project_id INTEGER REFERENCES projects(id),  -- 复活后的新项目ID（如重招）
    
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

三、核心算法逻辑（Python 伪代码）
3.1 精确资质匹配引擎（衔接Week 1标准库）

    class QualificationMatcher:
    """
    Week 2核心：基于Week 1的standard_certifications和ocr_extractions进行精确匹配
    """
    
    def __init__(self, project_id: int):
        self.project_id = project_id
        self.tender = db.get_tender_document(project_id)  # 招标文件解析结果
        self.bid_certs = db.get_ocr_extractions(project_id)  # Week 1 OCR提取的资质
        
    def exact_match_evaluation(self) -> dict:
        """
        执行精确匹配算法（非模糊匹配）
        """
        # 1. 解析招标文件要求（映射到标准编码）
        tender_requirements = self.parse_tender_requirements()
        
        fatal_missing = []
        optional_missing = []
        matched_list = []
        
        for req in tender_requirements:
            std_cert = db.get_standard_cert_by_code(req['cert_code'])
            matched = False
            
            # 在OCR提取的资质中寻找匹配
            for ocr_cert in self.bid_certs:
                if ocr_cert['field_name'] != 'cert_name':
                    continue
                
                normalized = self.normalize_ocr_text(ocr_cert['field_value'])
                
                # 精确匹配检查（Week 1定义的算法）
                if self.exact_match_check(normalized, std_cert):
                    # 进一步验证有效期（关键！）
                    valid_check = self.check_validity(
                        ocr_cert.get('valid_until'), 
                        self.tender.bid_open_date,
                        std_cert['validity_years']
                    )
                    
                    if valid_check['status'] == 'valid':
                        matched = True
                        matched_list.append({
                            'cert_code': std_cert['cert_code'],
                            'cert_name': std_cert['cert_full_name'],
                            'valid_until': ocr_cert.get('valid_until'),
                            'evidence_image_id': ocr_cert['image_id']
                        })
                    elif valid_check['status'] == 'expired':
                        fatal_missing.append({
                            'cert_code': std_cert['cert_code'],
                            'cert_name': std_cert['cert_full_name'],
                            'reason': 'expired',
                            'valid_until': ocr_cert.get('valid_until'),
                            'bid_open_date': self.tender.bid_open_date,
                            'severity': 'fatal'
                        })
                    elif valid_check['status'] == 'expiring_soon':
                        optional_missing.append({
                            'cert_code': std_cert['cert_code'],
                            'reason': 'expiring_soon',
                            'days_until_expire': valid_check['days_until_expire']
                        })
                    
                    break
            
            if not matched and req['is_mandatory']:
                if not any(m['cert_code'] == req['cert_code'] for m in fatal_missing):
                    fatal_missing.append({
                        'cert_code': req['cert_code'],
                        'cert_name': std_cert['cert_full_name'],
                        'reason': 'missing',
                        'severity': 'fatal'
                    })
            elif not matched and not req['is_mandatory']:
                optional_missing.append(req['cert_code'])
        
        # 计算匹配分数
        total_mandatory = len([r for r in tender_requirements if r['is_mandatory']])
        matched_mandatory = total_mandatory - len([m for m in fatal_missing if m['reason'] == 'missing'])
        score = int((matched_mandatory / total_mandatory) * 100) if total_mandatory > 0 else 100
        
        return {
            'qualification_match_score': score,
            'missing_mandatory_certs': fatal_missing,
            'missing_optional_certs': optional_missing,
            'matched_certs': matched_list,
            'is_qualification_pass': len([m for m in fatal_missing if m['reason'] in ['missing', 'expired']]) == 0
        }
    
    def exact_match_check(self, normalized: dict, std_cert: dict) -> bool:
        """
        Week 1定义的精确匹配算法（证书名称、等级、编号规则）
        """
        cleaned_name = normalized['cleaned_name']
        
        # 1. 必须包含所有required_keywords
        required = json.loads(std_cert['required_keywords'])
        for keyword in required:
            if keyword not in cleaned_name:
                return False
        
        # 2. 必须不包含任何exclude_keywords
        excluded = json.loads(std_cert['exclude_keywords'])
        for keyword in excluded:
            if keyword in cleaned_name:
                return False
        
        # 3. 等级精确匹配（一级≠二级）
        if std_cert['cert_code'] in ['CONSTRUCTION-GENERAL-1', 'FOOD-BUSINESS-LICENSE']:
            level_required = '一级' if '一级' in std_cert['cert_full_name'] else \
                           '二级' if '二级' in std_cert['cert_full_name'] else None
            if level_required and normalized.get('level_keyword') != level_required:
                return False
        
        # 4. 编号规则验证（如有）
        if normalized.get('cert_number') and std_cert['cert_number_pattern']:
            if not re.match(std_cert['cert_number_pattern'], normalized['cert_number']):
                return False
        
        return True
    
    def check_validity(self, valid_until: date, bid_open_date: date, validity_years: int) -> dict:
        """
        检查资质有效期是否覆盖开标日
        """
        if not valid_until:
            return {'status': 'unknown'}
        
        if valid_until < bid_open_date:
            return {'status': 'expired', 'days_past': (bid_open_date - valid_until).days}
        
        if valid_until < bid_open_date + timedelta(days=90):
            return {
                'status': 'expiring_soon',
                'days_until_expire': (valid_until - bid_open_date).days,
                'message': '资质将在开标后90天内过期'
            }
        
        return {'status': 'valid', 'days_valid': (valid_until - bid_open_date).days}
3.2 初筛报告生成引擎

    class EvaluationReportEngine:
    def __init__(self, project_id: int):
        self.project_id = project_id
        self.project = db.get_project(project_id)
        
    def generate_report(self) -> dict:
        """
        生成完整初筛报告
        """
        # 1. 资质评估（调用精确匹配）
        qual_result = QualificationMatcher(self.project_id).exact_match_evaluation()
        
        # 2. 时间评估
        time_result = self.calculate_time_urgency(
            self.tender.bid_open_date, 
            datetime.now()
        )
        
        # 3. 业主画像与关系指数
        owner_result = self.calculate_relationship_index(
            self.project.owner_unit,
            self.project.owner_type
        )
        
        # 4. 成本估算（Week 4定价的基础）
        cost_result = self.estimate_cost(
            self.tender.budget_amount,
            self.project.project_type,
            self.project.region
        )
        
        # 5. 综合概率计算（启发式算法，Week 8后用ML替代）
        win_prob = self.calculate_win_probability(
            qual_score=qual_result['qualification_match_score'],
            time_sufficient=time_result['is_time_sufficient'],
            relationship_index=owner_result['relationship_index'],
            cost_confidence=cost_result['confidence']
        )
        
        # 6. 风险汇总与建议
        fatal_risks = []
        warning_risks = []
        
        if not qual_result['is_qualification_pass']:
            fatal_risks.append({
                'type': 'qualification',
                'message': f"缺失强制资质：{', '.join([c['cert_name'] for c in qual_result['missing_mandatory_certs'] if c['reason'] == 'missing'])}",
                'details': qual_result['missing_mandatory_certs']
            })
        
        if time_result['time_urgency_level'] == 'expired':
            fatal_risks.append({
                'type': 'time',
                'message': '开标时间已过，无法投标'
            })
        
        # 系统建议
        if fatal_risks:
            recommendation = 'abandon'
            rec_reason = f"存在致命风险：{fatal_risks[0]['message']}"
        elif win_prob > 0.7:
            recommendation = 'worth_bidding'
            rec_reason = '资质匹配度高，时间充裕，建议投标'
        elif win_prob > 0.4:
            recommendation = 'worth_bidding' if owner_result['relationship_index'] > 30 else 'conditional'
            rec_reason = '有条件投标：需加强技术标优化或价格策略'
        else:
            recommendation = 'abandon'
            rec_reason = '中标概率较低，建议放弃（除非有内幕关系可标记）'
        
        # 7. 保存报告
        report_data = {
            'project_id': self.project_id,
            'qualification_match_score': qual_result['qualification_match_score'],
            'missing_mandatory_certs': json.dumps(qual_result['missing_mandatory_certs']),
            'missing_optional_certs': json.dumps(qual_result['missing_optional_certs']),
            'days_until_bid_open': time_result['days_until_bid_open'],
            'time_urgency_level': time_result['time_urgency_level'],
            'is_time_sufficient': time_result['is_time_sufficient'],
            'owner_profile_id': owner_result['owner_profile_id'],
            'relationship_index': owner_result['relationship_index'],
            'is_new_owner': owner_result['is_new_owner'],
            'estimated_cost': cost_result['estimated_cost'],
            'suggested_price_range_low': cost_result['low_price'],
            'suggested_price_range_high': cost_result['high_price'],
            'cost_estimate_confidence': cost_result['confidence'],
            'overall_win_probability': win_prob,
            'risk_level': 'high' if fatal_risks else ('medium' if warning_risks else 'low'),
            'fatal_risks': json.dumps(fatal_risks),
            'warning_risks': json.dumps(warning_risks),
            'recommendation': recommendation,
            'recommendation_reason': rec_reason
        }
        
        report_id = db.insert('bid_evaluation_reports', report_data)
        
        return {
            'report_id': report_id,
            **report_data,
            'qualification_detail': qual_result,
            'time_detail': time_result,
            'owner_detail': owner_result
        }
    
    def calculate_time_urgency(self, bid_open_date: datetime, current: datetime) -> dict:
        """
        时间充裕度计算（Week 2业务规则）
        """
        days_remaining = (bid_open_date - current).days
        
        if days_remaining < 0:
            return {
                'days_until_bid_open': days_remaining,
                'time_urgency_level': 'expired',
                'is_time_sufficient': False,
                'message': '开标时间已过'
            }
        elif days_remaining <= 3:
            level = 'urgent'
            sufficient = False
        elif days_remaining <= 7:
            level = 'tight'
            sufficient = True
        elif days_remaining <= 15:
            level = 'normal'
            sufficient = True
        else:
            level = 'relaxed'
            sufficient = True
        
        return {
            'days_until_bid_open': days_remaining,
            'time_urgency_level': level,
            'is_time_sufficient': sufficient,
            'working_days_estimate': days_remaining * 0.7
        }
    
    def calculate_relationship_index(self, owner_name: str, owner_type: str) -> dict:
        """
        关系指数计算（0=无，>0=有）
        """
        profile = db.query("""
            SELECT * FROM owner_profiles 
            WHERE owner_name = %s AND owner_type = %s
        """, owner_name, owner_type)
        
        if not profile:
            return {
                'owner_profile_id': None,
                'relationship_index': 0,
                'relationship_level': 'none',
                'is_new_owner': True,
                'cooperation_history': []
            }
        
        # 有合作即>0，具体数值基于合作次数（但只要有就算"有"）
        base_score = min(profile['cooperation_count'] * 20, 60)  # 最高60
        
        # 合作时间衰减（越近越好）
        if profile['last_cooperation_date']:
            months_ago = (datetime.now() - profile['last_cooperation_date']).days / 30
            if months_ago <= 6:
                base_score += 20
            elif months_ago <= 12:
                base_score += 10
        
        return {
            'owner_profile_id': profile['id'],
            'relationship_index': min(base_score, 100),
            'relationship_level': profile['relationship_level'],
            'is_new_owner': False,
            'cooperation_count': profile['cooperation_count'],
            'last_cooperation_date': profile['last_cooperation_date'],
            'avg_winning_discount': profile['avg_winning_discount']
        }
    
    def estimate_cost(self, budget: float, project_type: str, region: str) -> dict:
        """
        成本估算（基于历史数据或行业经验）
        """
        # 查找历史相似项目
        similar = db.query("""
            SELECT our_cost, bid_date 
            FROM price_history 
            WHERE project_type = %s AND region = %s
            AND ABS(budget_amount - %s) / %s < 0.2
            ORDER BY bid_date DESC LIMIT 5
        """, project_type, region, budget, budget)
        
        if similar:
            avg_cost = sum(s['our_cost'] for s in similar) / len(similar)
            # 通胀调整（假设年5%）
            years = (datetime.now() - similar[0]['bid_date']).days / 365
            estimated = avg_cost * (1.05 ** years)
            confidence = 'high' if len(similar) >= 3 else 'medium'
        else:
            # 冷启动：预算×75%
            estimated = budget * 0.75
            confidence = 'low'
        
        return {
            'estimated_cost': estimated,
            'low_price': estimated * 1.02,  # +2%
            'high_price': estimated * 1.15, # +15%
            'confidence': confidence
        }
3.3 审批流实现（选项A模式）

    class ApprovalWorkflowService:
    """
    实现选项A：专员独立审批 + 老板事后推翻
    """
    
    @staticmethod
    def specialist_decide(project_id: int, decision: str, reason: str, specialist_id: int) -> dict:
        """
        专员审批决策（立即生效）
        """
        # 获取最新报告
        report = db.get_latest_evaluation_report(project_id)
        
        # 如果系统检测到致命风险但专员仍要投，强制要求理由
        fatal_risks = json.loads(report['fatal_risks'])
        if decision == 'worthy' and fatal_risks and not reason:
            raise HTTPException(400, "存在致命风险仍标记worthy，必须填写覆盖理由")
        
        # 更新报告状态
        db.update('bid_evaluation_reports', {
            'id': report['id'],
            'confirmed_by_specialist': True,
            'specialist_decision': decision,
            'specialist_notes': reason,
            'confirmed_at': datetime.now()
        })
        
        # 更新项目状态（立即生效）
        new_status = 'approved_by_specialist' if decision == 'worthy' else 'rejected_by_specialist'
        db.update_project_status(project_id, new_status)
        
        # 如worthy，创建Week 3任务
        if decision == 'worthy':
            db.insert('tech_proposal_tasks', {
                'project_id': project_id,
                'status': 'pending_initiation'
            })
        
        # 记录日志
        db.insert('approval_logs', {
            'project_id': project_id,
            'action_type': f'specialist_{decision}',
            'actor_role': 'specialist',
            'actor_id': specialist_id,
            'reason_text': reason,
            'original_status': 'evaluation_ready',
            'new_status': new_status
        })
        
        # 通知老板（异步，不阻塞流程）
        notify_boss(
            title=f"专员已审批项目 {report['project_name']}",
            content=f"决策：{decision}，{'请查看详情' if decision == 'unworthy' else '已进入技术标生成阶段'}",
            project_id=project_id,
            urgency='normal' if decision == 'worthy' else 'high'
        )
        
        return {'status': 'success', 'project_status': new_status}
    
    @staticmethod
    def boss_override(project_id: int, action: str, reason: str, boss_id: int) -> dict:
        """
        老板推翻决策（事后监督权）
        action: 'revive' (unworthy→worthy) 或 'terminate' (worthy→unworthy强制终止)
        """
        project = db.get_project(project_id)
        current_status = project['status']
        
        if action == 'terminate':
            # 强制终止：worthy→unworthy
            if current_status != 'approved_by_specialist':
                raise HTTPException(400, "项目不在可终止状态")
            
            # 如有Week 3已生成内容，移入废弃库（Week 5机制，Week 2先标记）
            db.update_project_status(project_id, 'terminated_by_boss')
            
            # 创建废弃记录（供Week 6复活使用）
            db.insert('discarded_projects', {
                'project_id': project_id,
                'discarded_by': 'boss',
                'discard_reason': f"[老板终止] {reason}",
                'discard_stage': current_status
            })
            
            new_status = 'terminated_by_boss'
            
        elif action == 'revive':
            # 复活：unworthy→worthy
            if current_status != 'rejected_by_specialist':
                raise HTTPException(400, "项目不在可复活状态")
            
            db.update_project_status(project_id, 'approved_by_specialist')
            
            # 恢复Week 3任务
            db.upsert('tech_proposal_tasks', {
                'project_id': project_id,
                'status': 'pending_initiation'
            })
            
            new_status = 'approved_by_specialist'
        
        # 记录推翻日志
        db.insert('approval_logs', {
            'project_id': project_id,
            'action_type': f'boss_override_{action}',
            'actor_role': 'boss',
            'actor_id': boss_id,
            'reason_text': reason,
            'original_status': current_status,
            'new_status': new_status
        })
        
        # 强通知专员
        notify_specialist(
            title=f"老板{'终止' if action == 'terminate' else '复活'}项目：{project['project_name']}",
            content=f"理由：{reason}",
            urgency='urgent'
        )
        
        return {'status': 'success', 'new_status': new_status}
四、API 接口定义
Python
复制
#POST /api/projects/{project_id}/evaluation/initiate
#触发初筛报告生成（专员确认解析结果后调用）
#Response: {report_id, status: 'generating'}

#GET /api/evaluation-reports/{report_id}
#获取完整初筛报告（专员审批界面、老板监督台）
#Response: 包含资质匹配详情、时间分析、业主画像、财务估算、风险列表、系统建议

#POST /api/evaluation-reports/{report_id}/decide
#专员审批决策（选项A核心）
class SpecialistDecision(BaseModel):
    decision: str  # 'worthy' 或 'unworthy'
    reason: str      # 必填，特别是覆盖系统建议时

#ET /api/boss/oversight-dashboard
#老板监督台（今日专员已审批项目）
#Response: {today_approved: [...], today_rejected: [...], revivable_discarded: [...]}

#POST /api/projects/{project_id}/override
#老板推翻决策
class BossOverride(BaseModel):
    action: str      # 'revive' 或 'terminate'
    reason: str      # 必填

#GET /api/discarded-projects
#放弃库列表（可复活项目）
#Query: ?can_revive=true&owner_type=school

#POST /api/discarded-projects/{id}/revive
#复活废弃项目（创建新项目或恢复原项目）
五、前端界面设计
5.1 初筛报告展示页（专员决策主界面）

┌─────────────────────────────────────────────────────────────────────┐
│ 项目：XX学校食堂配送    预算：150万    开标：2026-04-15 (20天剩余)     │
├─────────────────────────────────────────────────────────────────────┤
│ 左侧：关键指标卡片        │  右侧：详细分析                           │
├─────────────────────────┼───────────────────────────────────────────┤
│                         │                                           │
│ 资质匹配度              │  【资质匹配详情】                          │
│ ┌───────────────────┐   │  ✅ 食品经营许可证（有效期至2027-03）       │
│ │      85%          │   │  ✅ ISO22000（有效期至2026-12）           │
│ │    [环形图]       │   │  ❌ HACCP（缺失，加分项）                  │
│ │                   │   │  ⚠️ 营业执照（即将过期，建议更新）          │
│ └───────────────────┘   │                                           │
│                         │  【时间分析】                              │
│ 时间充裕度              │  剩余20天（约14个工作日）                    │
│ [ 正常 蓝色 ]           │  状态：正常（建议Week 3立即启动）            │
│                         │                                           │
│ 关系指数                │  【业主画像】                                │
│ [ 30/100 黄色 ]         │  首次合作（XX市第一中学）                    │
│ 首次接触                │  历史偏好：重技术方案、轻价格竞争            │
│                         │                                           │
│ 预估中标率              │  【财务估算】                                │
│ [ 52% 黄色 ]            │  预估成本：112万（置信度：低，基于预算比例）   │
│                         │  建议报价：114-129万                        │
├─────────────────────────┴───────────────────────────────────────────┤
│ 风险预警                                                            │
│ 🔴 致命风险：无                                                     │
│ 🟡 警告：业主为首次接触，无历史关系；成本估算置信度低，需财务复核      │
├─────────────────────────────────────────────────────────────────────┤
│ 系统建议：有条件投标（中标概率52%，建议优化技术标或评估价格竞争力）     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ [    worthy    ]    [   unworthy   ]                               │
│ 填写审批理由（如覆盖系统建议需详述）：                               │
│ ___________________________________________                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

5.2 老板监督台（Oversight Dashboard）
今日投标态势（2026-03-24）
┌─────────────────────────────────────────────────────────────────────┐
│ 专员已审批项目（3个）                                               │
├──────────────┬──────────┬──────────┬──────────┬────────────────┤
│ 项目名称       │ 专员决策 │ 系统建议 │ 中标概率 │ 操作           │
├──────────────┼──────────┼──────────┼──────────┼────────────────┤
│ XX中学食堂     │ worthy   │ worth    │ 75%      │ [查看]         │
│ XX政府物业     │ worthy   │ abandon  │ 35%      │ [推翻终止] ⚠️  │ ← 系统建议放弃但专员投了
│ XX小学配送     │ unworthy │ abandon  │ 15%      │ [复活]         │ ← 可一键复活
└──────────────┴──────────┴──────────┴──────────┴────────────────┘

放弃库（近7天）
┌──────────────┬──────────┬──────────┬────────────────────────────┐
│ XX医院食堂   │ 资质不符 │ 03-20    │ [复活] [查看历史报告]       │
│ XX单位物业   │ 时间不够 │ 03-22    │ [复活]                      │
└──────────────┴──────────┴──────────┴────────────────────────────┘

待处理提醒：1个项目（XX政府物业）系统建议放弃但被专员标记worthy，建议审核

六、关键业务校验规则
资质致命拦截：missing_mandatory_certs 中存在 reason='expired' 或 reason='missing' 时，专员标记 worthy 必须填写覆盖理由（至少10字）。
时间过期拦截：time_urgency_level='expired' 时，系统禁止标记 worthy，只能 unworthy。
审批立即生效：专员点击 worthy 后，项目状态立即变为 approved_by_specialist，不等待老板操作。
推翻强制理由：老板执行 override 操作必须填写理由，记录到 approval_logs。
复活限制：只能复活状态为 rejected_by_specialist 且 can_be_revived=true 的项目。
七、交付标准（Week 2 验收 checklist）
[ ] 上传资质扫描件（含过期证书），系统精确匹配并标记红色致命项（有效期检查）
[ ] 初筛报告展示：资质匹配度百分比、时间充裕度标签、业主画像（首次接触识别）
[ ] 专员点击 worthy 后，项目立即进入 "approved_by_specialist" 状态，老板监督台显示记录
[ ] 老板点击【推翻终止】，项目状态变为 "terminated_by_boss"，专员收到强通知
[ ] 老板在放弃库点击【复活】，unworthy 项目恢复为 worthy，进入 Week 3 流程
[ ] 审批日志 approval_logs 完整记录所有操作（专员审批、老板推翻、复活）

Week 2 核心是决策引擎与权限控制。务必确保：
与 Week 1 的 standard_certifications 和 ocr_extractions 表正确关联（外键查询）
精确匹配算法严格实现（一级≠二级，经营≠生产）
审批状态机严谨：专员审批立即生效，老板事后推翻有完整审计日志
初筛报告的前端展示突出"致命风险"（红色），防止专员误判