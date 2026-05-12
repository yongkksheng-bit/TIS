Week 8 开发文档：智能化进阶与生态扩展（Advanced AI & Automation）
文档元信息
开发周期：Week 8（5个工作日，MVP后首个迭代）
依赖前提：Week 1-7 生产环境已稳定运行，积累至少 20+ 新项目数据（脱离冷启动）
核心业务目标：从"人工辅助"进化为"智能预判"，实现竞争对手监控、AI定价模型自训练、移动端轻量操作
关键价值：降低 50% 重复操作时间，提前 48 小时预警竞争态势变化
一、业务逻辑架构（Week 8 核心场景）
1.1 场景 A：竞争对手自动驾驶舱
自动爬取政府采购网、学校官网，发现新招标公告时自动推送
监控特定竞争对手（如"XX餐饮公司"）的投标动态：最近投了哪些项目、报价下浮率趋势、资质变化
预警：当竞争对手在你跟踪的项目中也报名时，立即推送"竞争警报"
1.2 场景 B：AI 定价大脑（从规则到 ML）
Week 4 使用规则算法（冷启动），Week 8 基于积累的 20+ 项目数据训练 XGBoost/LightGBM 定价模型
输入：项目特征（预算、地区、类型、业主关系指数、竞争对手数量）
输出：最优报价（期望收益最大化）+ 中标概率置信区间
自动迭代：每新增 5 个中标结果，自动重训练模型
1.3 场景 C：移动端标书助手（小程序/App）
标书专员外出考察现场时，手机拍照上传招标文件关键页，OCR 自动识别并解析
老板出差时，手机端审批定价决策（语音输入差异原因）
开标前 2 小时手机提醒，查看封装清单（扫码核对）
1.4 场景 D：智能知识问答（RAG Chatbot）
专员提问："ISO22000 和 HACCP 有什么区别？哪个对学校食堂更加分？"
系统基于 Week 3 知识库自动回答，并引用历史中标案例佐证
提问："这个项目缺个面点师资格证，能用中级厨师证代替吗？" → 检索资质库和废标陷阱库回答

二、数据库表设计（SQL）

    -- 竞争对手监控库（自动驾驶舱核心）
    CREATE TABLE competitor_monitoring (
    id SERIAL PRIMARY KEY,
    competitor_name VARCHAR(255) NOT NULL,  -- 监控对象
    competitor_aliases JSONB,               -- 别名（如"XX餐饮"又名"XX团餐"）
    
    -- 监控规则
    monitor_regions JSONB,                -- ["北京市", "上海市"]
    monitor_project_types JSONB,          -- ["学校食堂", "政府物业"]
    alert_threshold_discount DECIMAL(5,2), -- 对手报价低于此下浮率时预警（如0.15）
    
    -- 抓取数据缓存
    last_seen_projects JSONB,             -- [{project_name, bid_date, price, win},...]
    bidding_trend JSONB,                  -- 近3个月投标频率、胜率、平均下浮率
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- AI 定价模型版本库（模型迭代管理）
    CREATE TABLE pricing_ml_models (
    id SERIAL PRIMARY KEY,
    model_version VARCHAR(20),              -- v1.0, v1.1...
    model_type VARCHAR(50),               -- xgboost / lightgbm / neural_network
    training_data_range JSONB,            -- {from_date, to_date, sample_count}
    model_performance JSONB,              -- {accuracy: 0.82, f1_score: 0.79, rmse: 0.05}
    model_file_path VARCHAR(500),         -- MinIO 存储路径（pickle/joblib）
    feature_importance JSONB,             -- {budget_weight: 0.3, relationship_weight: 0.25...}
    is_production BOOLEAN DEFAULT FALSE,  -- 是否生产环境在用
    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deployed_at TIMESTAMP
    );

    -- 移动端操作日志（同步与审计）
    CREATE TABLE mobile_operations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    device_type VARCHAR(50),              -- ios / android / mini_program
    operation_type VARCHAR(50),           -- photo_upload / voice_decision / quick_approve
    project_id INTEGER REFERENCES projects(id),
    payload JSONB,                        -- 操作详情（如图片路径、语音转文字结果）
    sync_status VARCHAR(20),              -- synced / pending / conflict
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 智能问答会话库（RAG Chatbot）
    CREATE TABLE ai_chat_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    session_context JSONB,                -- 关联项目ID、当前阶段等上下文
    
    -- 问答对
    question TEXT,
    question_vector vector(1536),         -- 向量化用于相似问题检索
    retrieved_chunks JSONB,               -- 检索到的知识块ID
    generated_answer TEXT,
    user_feedback INTEGER CHECK (user_feedback IN (1, -1, 0)), -- 1满意 -1不满意 0未评
    feedback_reason TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

    -- 自动化任务队列（爬虫、模型训练、数据清洗）
    CREATE TABLE automation_tasks (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50),                -- crawler / model_training / data_cleanup
    task_name VARCHAR(255),
    cron_expression VARCHAR(50),          -- 定时规则（如"0 2 * * *"每天2点）
    last_run_at TIMESTAMP,
    last_status VARCHAR(20),              -- success / failed / running
    last_output TEXT,
    is_enabled BOOLEAN DEFAULT TRUE
    ); 

三、核心功能模块（开发指令）
3.1 竞争对手自动驾驶舱（Auto-Competitor Intelligence）

    class CompetitorAutoMonitor:
    def __init__(self):
        self.crawler = DistributedCrawler()  # 分布式爬虫基座
        self.analyzer = CompetitorAnalyzer()
    
    async def daily_crawl_job(self):
        """
        每日凌晨2点执行：爬取指定网站，更新竞争对手动态
        """
        targets = [
            'http://www.ccgp.gov.cn',           # 中国政府采购网
            'http://ggzyjyw.beijing.gov.cn',    # 北京公共资源交易（示例）
            # 各省市政府采购网配置在表 automation_tasks 中
        ]
        
        for target in targets:
            # 抓取昨日新增中标公告
            announcements = await self.crawler.fetch(
                url=target,
                date_range=(datetime.now() - timedelta(days=1), datetime.now()),
                keywords=['食堂', '物业', '配送']  # 业务关键词过滤
            )
            
            for ann in announcements:
                # 解析结构化数据（中标单位、金额、项目类型）
                parsed = self.analyzer.parse_announcement(ann['content'])
                
                # 匹配监控列表
                matched_competitor = self.match_competitor(parsed['winner_name'])
                
                if matched_competitor:
                    # 更新竞争对手数据库
                    self.update_competitor_stats(matched_competitor.id, parsed)
                    
                    # 检查是否与我方正在跟踪的项目冲突
                    conflict_alert = self.check_conflict_with_my_projects(parsed)
                    if conflict_alert:
                        await self.push_alert(conflict_alert)
    
    def check_conflict_with_my_projects(self, competitor_bid: dict) -> dict:
        """
        检测对手投标是否与我方项目冲突（同一项目）
        """
        my_active_projects = db.query("""
            SELECT * FROM projects 
            WHERE status IN ('approved_by_specialist', 'awaiting_pricing', 'formal_review')
            AND bid_open_date > NOW()
        """)
        
        for my_proj in my_active_projects:
            # 相似度判断（项目名称、预算、开标时间接近）
            if similarity(my_proj['name'], competitor_bid['project_name']) > 0.8 \
               and abs(my_proj['budget'] - competitor_bid['budget']) / my_proj['budget'] < 0.1:
                
                return {
                    'alert_type': 'competitor_joined_same_project',
                    'severity': 'high',
                    'my_project_id': my_proj['id'],
                    'competitor_name': competitor_bid['winner_name'],
                    'competitor_historical_discount': self.get_avg_discount(competitor_bid['winner_name']),
                    'suggestion': f"竞争对手{competitor_bid['winner_name']}已参与此项目，历史平均下浮率{self.get_avg_discount}%"
                }
        
        return None
    
    def generate_competitor_report(self, competitor_id: int) -> dict:
        """
        生成竞争对手深度分析报告（供老板制定策略）
        """
        stats = db.query("""
            SELECT 
                COUNT(*) as total_bids,
                SUM(CASE WHEN is_win THEN 1 ELSE 0 END) as wins,
                AVG(discount_rate) as avg_discount,
                AVG(winning_price) as avg_price,
                MODE() WITHIN GROUP (ORDER BY project_type) as preferred_type
            FROM price_history 
            WHERE winning_unit = %s
            AND bid_date > NOW() - INTERVAL '6 months'
        """, competitor_id)
        
        return {
            'competitor_name': competitor_id,
            'win_rate_last_6m': stats['wins'] / stats['total_bids'],
            'bidding_strategy': 'aggressive_low_price' if stats['avg_discount'] > 0.1 else 'value_based',
            'strength_regions': self.get_regions(competitor_id),
            'recent_weakness': self.detect_weakness(competitor_id),  # 近期连续未中标类型
            'recommended_counter_strategy': 'differentiation' if stats['avg_discount'] > 0.1 else 'price_match'
        }
3.2 AI 定价模型训练与部署（从规则到 ML）

    class AIPricingEngine:
    def __init__(self):
        self.current_model = self.load_production_model()
    
    def load_production_model(self):
        """加载当前生产环境模型"""
        model_record = db.query("""
            SELECT * FROM pricing_ml_models 
            WHERE is_production = true 
            ORDER BY deployed_at DESC LIMIT 1
        """)
        if model_record:
            return joblib.load(model_record['model_file_path'])
        return None  # 冷启动时返回None，使用Week 4规则引擎
    
    def prepare_training_data(self) -> pd.DataFrame:
        """
        从Week 1-7积累的数据准备训练集
        """
        # 特征工程
        data = db.query("""
            SELECT 
                p.budget_amount as budget,
                p.owner_type,
                p.region,
                ber.relationship_index / 100.0 as relationship,
                ber.days_until_bid_open as urgency,
                COUNT(ph.winning_unit) as competitor_count,  -- 竞争对手数量（从price_history估算）
                bo.final_bid_price as our_price,
                bo.winning_price as market_price,
                CASE WHEN bo.outcome_status = 'win' THEN 1 ELSE 0 END as is_win
            FROM projects p
            JOIN bid_evaluation_reports ber ON ber.project_id = p.id
            JOIN bid_outcomes bo ON bo.project_id = p.id
            LEFT JOIN price_history ph ON ph.project_type = p.project_type 
                AND ABS(ph.budget_amount - p.budget_amount) / p.budget_amount < 0.2
                AND ph.bid_date BETWEEN p.created_at - INTERVAL '30 days' AND p.created_at
            WHERE bo.outcome_status IN ('win', 'lose')  -- 只取有明确结果的
            AND p.created_at > NOW() - INTERVAL '6 months'  -- 近6个月数据
            GROUP BY p.id, bo.final_bid_price, bo.winning_price, bo.outcome_status
        """)
        
        df = pd.DataFrame(data)
        
        # 特征编码
        df['owner_type_encoded'] = LabelEncoder().fit_transform(df['owner_type'])
        df['region_encoded'] = LabelEncoder().fit_transform(df['region'])
        
        # 目标变量：中标概率（需要平滑处理，因为结果是0/1）
        # 实际训练时可能用 is_win 作为二分类，或用 price_rank 作为回归
        
        return df
    
    def train_new_model(self) -> dict:
        """
        训练新模型（当积累20+数据后，优于Week 4规则引擎）
        """
        df = self.prepare_training_data()
        
        if len(df) < 20:
            return {'status': 'insufficient_data', 'required': 20, 'current': len(df)}
        
        # 特征/目标
        X = df[['budget', 'owner_type_encoded', 'region_encoded', 
                'relationship', 'urgency', 'competitor_count']]
        y = df['is_win']  # 二分类：中/不中
        
        # 训练/测试分割
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
        
        # XGBoost 模型（可解释性强，适合投标场景）
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            objective='binary:logistic'
        )
        
        model.fit(X_train, y_train)
        
        # 评估
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)
        
        # 特征重要性（可解释性，老板要知道为什么推荐这个价）
        importance = dict(zip(X.columns, model.feature_importances_))
        
        # 保存模型
        model_version = f"v{datetime.now().strftime('%Y%m%d')}"
        file_path = f"/models/pricing_model_{model_version}.pkl"
        joblib.dump(model, file_path)
        
        # 入库
        model_id = db.insert('pricing_ml_models', {
            'model_version': model_version,
            'model_type': 'xgboost',
            'training_data_range': json.dumps({
                'from_date': str(df['created_at'].min()),
                'to_date': str(df['created_at'].max()),
                'sample_count': len(df)
            }),
            'model_performance': json.dumps({'accuracy': accuracy, 'f1_score': f1}),
            'model_file_path': file_path,
            'feature_importance': json.dumps(importance),
            'is_production': False  # 先不自动上线，需人工确认
        })
        
        return {
            'model_id': model_id,
            'version': model_version,
            'accuracy': accuracy,
            'feature_importance': importance,
            'suggestion': '模型表现良好，建议人工审核后切换至生产环境'
        }
    
    def predict_with_ml(self, project_features: dict) -> dict:
        """
        使用ML模型预测（替代Week 4规则引擎）
        """
        if not self.current_model:
            return {'fallback_to_rules': True}  # 回退到Week 4
        
        # 特征编码（需与训练时一致）
        X = pd.DataFrame([{
            'budget': project_features['budget'],
            'owner_type_encoded': self.encode_owner(project_features['owner_type']),
            'region_encoded': self.encode_region(project_features['region']),
            'relationship': project_features['relationship_index'] / 100,
            'urgency': project_features['days_remaining'],
            'competitor_count': project_features.get('estimated_competitors', 3)
        }])
        
        # 预测概率
        win_prob = self.current_model.predict_proba(X)[0][1]
        
        # 最优价格搜索（网格搜索期望收益最大化）
        best_price = self.search_optimal_price(
            project_features, 
            win_prob_func=lambda price: self.estimate_prob_at_price(price, X)
        )
        
        return {
            'model_version': self.current_model.version,
            'win_probability': win_prob,
            'optimal_price': best_price['price'],
            'expected_profit': best_price['expected_profit'],
            'confidence_interval': best_price['ci'],
            'feature_importance': self.get_feature_importance_explanation(X)  # 解释为什么是这个概率
        }
    
    def search_optimal_price(self, base_features: dict, win_prob_func: callable) -> dict:
        """
        网格搜索最优价格（期望收益最大化）
        """
        cost = base_features['cost_base']
        budget = base_features['budget_limit']
        
        best_expectation = 0
        best_price = cost * 1.1  # 默认
        results = []
        
        for markup in [0.02, 0.03, 0.05, 0.08, 0.10, 0.12, 0.15]:
            price = cost * (1 + markup)
            if price > budget * 0.95:  # 限价约束
                continue
            
            prob = win_prob_func(price)  # 使用模型预测该价格下的中标概率
            profit = price - cost
            expectation = profit * prob
            
            results.append({'price': price, 'prob': prob, 'profit': profit, 'expectation': expectation})
            
            if expectation > best_expectation:
                best_expectation = expectation
                best_price = price
        
        return {
            'price': best_price,
            'expected_profit': best_expectation,
            'scenarios': results,
            'ci': [r['expectation'] for r in results]  # 置信区间简化版
        }

3.3 移动端轻量化操作（小程序/App）

    class MobileAPIService:
    """
    移动端专用API（简化版，适合4G网络和小屏幕）
    """
    
    async def photo_quick_upload(self, file: UploadFile, user_id: int) -> dict:
        """
        手机拍照上传招标文件关键页，OCR自动解析并创建草稿项目
        """
        # 保存图片
        img_path = f"/mobile_uploads/{uuid4()}.jpg"
        with open(img_path, "wb") as f:
            f.write(await file.read())
        
        # OCR识别（使用Week 1引擎，但简化流程）
        ocr_result = await ocr_engine.recognize(img_path)
        
        # 快速提取关键信息（项目名称、预算、时间）
        key_info = llm_client.extract([
            {"role": "system", "content": "从招标公告OCR文本中提取关键信息，返回JSON"},
            {"role": "user", "content": ocr_result['text'][:2000]}  # 限制长度
        ])
        
        # 创建草稿项目（待PC端完善）
        draft_id = db.insert('projects', {
            'project_name': key_info['name'] + '（手机草稿）',
            'budget_amount': key_info['budget'],
            'bid_open_date': key_info['date'],
            'status': 'mobile_draft',
            'created_by': user_id
        })
        
        return {
            'draft_id': draft_id,
            'extracted_info': key_info,
            'message': '草稿已创建，请在PC端完善并上传完整招标文件',
            'pc_continue_url': f'https://your-system.com/projects/{draft_id}/continue'
        }
    
    async def voice_decision_record(self, project_id: int, audio_file: UploadFile, user_id: int) -> dict:
        """
        语音录入定价决策差异原因（老板出差时）
        """
        # 语音转文字（ASR，可用讯飞/腾讯API）
        text = await asr_service.transcribe(audio_file)
        
        # 语义校验（确保说了原因，不是废话）
        if len(text) < 10 or '价格' not in text:
            return {'error': '语音内容过短或未提及价格决策，请重试'}
        
        # 保存到定价决策表（作为boss_decision_reason）
        db.update('pricing_decisions', {
            'project_id': project_id,
            'boss_decision_reason': f'[语音录入]{text}',
            'updated_by': user_id
        })
        
        return {'transcribed_text': text, 'saved': True}
    
    def get_mobile_dashboard(self, user_id: int, role: str) -> dict:
        """
        移动端首页（极度简化，只显示待办）
        """
        if role == 'boss':
            todos = db.query("""
                SELECT p.id, p.project_name, p.status, 
                       DATEDIFF(p.bid_open_date, NOW()) as days_left
                FROM projects p
                WHERE p.status = 'awaiting_pricing'  -- 等你定价
                ORDER BY p.bid_open_date ASC
                LIMIT 5
            """)
            return {'type': 'pending_decisions', 'items': todos}
        
        elif role == 'specialist':
            todos = db.query("""
                SELECT p.id, p.project_name, fri.check_title as urgent_task
                FROM projects p
                JOIN formal_review_items fri ON fri.project_id = p.id
                WHERE p.status = 'formal_review' 
                AND fri.risk_level = 'fatal'
                AND fri.specialist_status = 'pending'
                ORDER BY p.bid_open_date ASC
                LIMIT 5
            """)
            return {'type': 'urgent_reviews', 'items': todos}
        
        return {'type': 'empty'}

3.4 智能知识问答（RAG Chatbot）

    class KnowledgeChatbot:
    def __init__(self):
        self.embedding = DeepSeekClient()
        self.vector_store = PGVector()
    
    async def answer_question(self, question: str, context_project_id: int = None) -> dict:
        """
        基于Week 3知识库回答专业问题
        """
        # 1. 问题向量化
        q_vector = self.embedding.embed(question)
        
        # 2. 多路检索
        retrieved = self.vector_store.similarity_search(
            vector=q_vector,
            filters={'is_deprecated': False},
            top_k=5
        )
        
        # 3. 上下文构建（如有当前项目上下文）
        context_prompt = ""
        if context_project_id:
            project = db.get_project(context_project_id)
            context_prompt = f"当前项目背景：{project['name']}，业主类型：{project['owner_type']}，服务类型：食堂配送+物业。\n"
        
        # 4. 生成回答（带引用）
        prompt = f"""
        基于以下知识库内容，回答用户问题。如果涉及资质对比，必须严格区分不同证书的差异。
        
        {context_prompt}
        
        检索到的相关知识：
        {chr(10).join([f"[{i+1}] {r['content'][:300]}" for i, r in enumerate(retrieved)])}
        
        用户问题：{question}
        
        回答要求：
        1. 直接回答，不要废话
        2. 如涉及具体操作，给出步骤123
        3. 最后列出引用的知识来源编号[1][2]等
        4. 如果知识库不足以回答，明确说"需要补充资料"
        """
        
        answer = self.embedding.chat(prompt)
        
        # 5. 记录会话（用于后续优化）
        session_id = db.insert('ai_chat_sessions', {
            'user_id': current_user.id,
            'session_context': json.dumps({'project_id': context_project_id}),
            'question': question,
            'question_vector': q_vector,
            'retrieved_chunks': json.dumps([r['id'] for r in retrieved]),
            'generated_answer': answer
        })
        
        return {
            'answer': answer,
            'sources': [{'id': r['id'], 'title': r['metadata'].get('scene', '未知')} for r in retrieved],
            'session_id': session_id,
            'feedback_requested': True  # 前端显示 thumbs up/down
        }
    
    def answer_qualification_comparison(self, cert_a: str, cert_b: str) -> str:
        """
        专项：资质对比（如ISO22000 vs HACCP）
        检索标准资质库返回差异
        """
        a_info = db.get_standard_cert_by_name(cert_a)
        b_info = db.get_standard_cert_by_name(cert_b)
        
        if not a_info or not b_info:
            return "证书信息不在标准库中，请检查名称"
        
        return f"""
        {cert_a} vs {cert_b} 对比：
        
        1. 颁发机构：{a_info['issuing_authority_keywords']} vs {b_info['issuing_authority_keywords']}
        2. 有效期：{a_info['validity_years']}年 vs {b_info['validity_years']}年
        3. 适用场景：{a_info['category']} vs {b_info['category']}
        4. 学校食堂投标建议：{'优先' + cert_a if a_info['is_mandatory_for_food_delivery'] else '均可作为加分项'}
        
        历史中标案例：{self.get_cases_using_certs(cert_a, cert_b)}
        """

四、API 接口定义（Week 8 新增）

#竞争对手监控
#GET /api/competitors/dashboard
#Response: 监控列表、最近动态、冲突预警

#POST /api/competitors/{id}/analyze
#Response: 竞争对手深度分析报告（策略建议）

#AI 定价模型
#POST /api/ml-pricing/train
#触发模型训练（老板权限，数据足够时执行）

#GET /api/ml-pricing/status
#获取当前模型状态（冷启动规则 / ML模型 v1.2）

#POST /api/ml-pricing/predict
#Request: project_features
#Response: win_prob, optimal_price, confidence_interval, feature_importance

#移动端
#POST /api/mobile/photo-upload
#Content-Type: multipart/form-data
#Response: draft_id, extracted_info

#POST /api/mobile/voice-decision
#Content-Type: multipart/form-data (audio/mp3)
#Response: transcribed_text, saved_status

#GET /api/mobile/dashboard
#Response: simplified todo list

#智能问答
#POST /api/chat/ask
#Request: {question, project_id(optional), session_id(optional)}
#Response: answer, sources, session_id

#OST /api/chat/feedback
#Request: {session_id, feedback: 1/-1, reason}

五、前端界面设计（关键新增）
5.1 老板战略驾驶舱（Week 8 升级版）

┌─────────────────────────────────────────────────────────────────────┐
│ 战略驾驶舱（2026年4月）                    [AI模型：v1.2 准确率82%]    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  竞争态势雷达                                                        │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  监控竞争对手：5家                                             │ │
│  │  • XX餐饮（威胁等级：高） - 近1月投标3次，胜率67%，平均下浮12%   │ │
│  │  • YY团餐（威胁等级：中） - 近1月投标2次，胜率50%，平均下浮8%    │ │
│  │  🚨 预警：XX餐饮已报名你跟踪的"XX大学食堂项目"                 │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  AI定价大脑建议                                                     │
│  基于历史20个项目训练，模型建议：                                    │
│  • 当前项目最优报价：98.5万（期望收益：2.8万，中标概率：65%）        │
│  • 关键因子：关系指数(30%) > 预算规模(25%) > 竞争烈度(20%)          │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│ 自动化任务状态                                                     │
│ ☑ 每日爬虫（昨日抓取12条公告，3条匹配业务）                        │
│ ☑ 模型训练（数据不足20条，跳过）                                   │
│ ☐ 知识库清理（45个冷门段落待 review）                             │
└─────────────────────────────────────────────────────────────────────┘

5.2 移动端界面（小程序）
┌─────────────────┐
│  投标助手        │
├─────────────────┤
│  📷 拍照建档     │  ← 点击拍照上传招标公告
│  🎤 语音决策     │  ← 老板专用
│  📋 今日待办 (3) │
├─────────────────┤
│  紧急提醒        │
│  ⚠️ XX中学      │
│     明天开标，形式│
│     审查未完成    │
├─────────────────┤
│  [查看封装清单]  │  ← 扫码核对
│  [知识问答]      │  ← 提问"ISO22000有效期"
└─────────────────┘

六、交付标准（Week 8）
[ ] 配置 3 个竞争对手监控，每日自动爬取并推送动态
[ ] 积累 20+ 项目数据后，训练 XGBoost 定价模型，准确率 >75%
[ ] 手机拍照上传招标文件，自动创建草稿项目（OCR解析关键信息）
[ ] 语音录入定价决策，ASR 准确率 >90%
[ ] 知识问答可回答"XX资质 vs YY资质区别"类问题，引用历史案例
[ ] 系统自动化任务面板（爬虫、训练、清理的可视化配置）

Week 8 是智能化跃升，核心是从"人工驱动"到"数据驱动+自动化"。重点实现：
监控爬虫的健壮性（反爬处理、代理池）
ML模型的可解释性（老板要知道为什么推荐这个价，不能是黑盒）
移动端的极简交互（只保留高频核心功能）
问答系统的准确性（RAG检索质量决定回答质量）
Week 8 完成后，系统具备自进化能力，形成"投标-数据积累-模型优化-更准投标"的飞轮。