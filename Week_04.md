Week 4 开发文档：智能定价决策系统（IPDS）
文档元信息
开发周期：Week 4（5个工作日）
依赖前提：Week 1-3 已完成（数据库、文件解析、资质匹配、技术标生成）
核心业务目标：实现成本录入 → 博弈定价 → 版本控制 → 决策确认的完整闭环
关键限制：历史数据有限（11份文件），需处理冷启动问题
一、业务逻辑架构（必读）
1.1 定价决策 Workflow（核心流程）

[技术标确认完成] 
    ↓
[成本录入阶段] ← 三角色均可录入，系统记录"成本版本"
    ↓
[博弈定价计算] ← 基于历史数据+爬虫数据，生成概率-利润矩阵
    ↓
[定价决策界面] ← 展示：成本线 | 建议区间 | 博弈曲线 | 历史对标
    ↓
[财务建议价] ← 财务录入（可选）
    ↓
[老板决策价] ← 最终定价（必填），填写与系统建议的差异原因
    ↓
[价格回填技术标] ← 自动更新商务标报价部分
    ↓
[形式审查前置] ← 检查报价是否符合招标文件要求（如：不能超过预算价）

1.2 关键业务规则（硬性约束）
规则1：成本录入权限
老板、财务、标书专员均可录入/修改成本
每次修改生成新版本（cost_version），记录修改人、修改时间、修改理由
最终采用"最新确认版本"作为博弈计算基准
规则2：定价博弈模型（冷启动版）
由于历史数据只有11份，采用分层概率模型：

    #概率计算逻辑（数据不足时的工程化处理）
    if historical_similar_projects >= 5:
    # 数据充足：基于历史回归模型
    win_prob = regression_model(price, historical_wins)
    else:
    # 数据不足（冷启动）：基于规则的启发式算法
    base_prob = 0.5  # 基准概率
    price_score = calculate_price_score(price, budget)  # 价格分计算（基于招标文件规则）
    relation_boost = relationship_index * 0.3  # 关系加成
    time_decay = max(0, 1 - days_to_bid/30)  # 时间越近竞争越充分，概率递减
    
    win_prob = base_prob * price_score + relation_boost - time_decay

规则3：版本控制与差异追踪
必须记录三级价格：
system_suggested：系统基于成本+算法推荐
finance_suggested：财务建议价（可null）
boss_final：老板最终决策价（必填）
强制字段：如果 boss_final 与 system_suggested 差异 >5%，必须填写 decision_reason（如："预留谈判空间"、"竞争对手 likely 报低价"）
规则4：报价策略拦截
招标文件常有硬性限价（如：不得超过预算价95%），系统需前置拦截：
录入成本后，如果最低报价（成本+2%）> 限价，立即红色警告"成本倒挂，建议放弃"
老板定价时，如果定价 > 限价，强制二次确认

二、数据库表设计（SQL）

    -- 成本测算表（版本控制核心）
    CREATE TABLE cost_estimates (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    version_number INTEGER DEFAULT 1,  -- 成本版本号
    
    -- 成本明细（根据你的业务细化）
    food_cost DECIMAL(15,2) NOT NULL,           -- 食材成本（基于配送量测算）
    logistics_cost DECIMAL(15,2) NOT NULL,      -- 物流成本（油费、车辆折旧、冷链）
    labor_cost DECIMAL(15,2) NOT NULL,          -- 人工成本（配送员+厨师+物业人员）
    management_cost DECIMAL(15,2) NOT NULL,   -- 管理费用（办公、保险、税费）
    other_cost DECIMAL(15,2) DEFAULT 0,       -- 其他不可预见费
    
    total_cost DECIMAL(15,2) GENERATED ALWAYS AS 
        (food_cost + logistics_cost + labor_cost + management_cost + other_cost) STORED,
    
    -- 元数据
    estimated_by INTEGER REFERENCES users(id),  -- 录入人
    estimated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estimate_reason TEXT,  -- 测算依据（如："基于上学期实际配送量*1.1系数"）
    is_confirmed BOOLEAN DEFAULT FALSE,  -- 是否确认为最终成本基线
    
    UNIQUE(project_id, version_number)
    );

    -- 定价决策表（核心决策记录）
    CREATE TABLE pricing_decisions (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    cost_estimate_id INTEGER REFERENCES cost_estimates(id),  -- 关联的成本版本
    
    -- 三级价格（版本控制）
    cost_base DECIMAL(15,2) NOT NULL,                    -- 成本基线（来自cost_estimates）
    system_suggested_low DECIMAL(15,2) NOT NULL,         -- 系统建议下限（成本*1.02）
    system_suggested_high DECIMAL(15,2) NOT NULL,        -- 系统建议上限（成本*1.15）
    system_suggested_optimal DECIMAL(15,2),              -- 系统最优建议（博弈论计算）
    
    finance_suggested_price DECIMAL(15,2),               -- 财务建议价（可null）
    finance_suggestion_reason TEXT,                      -- 财务理由（如："考虑下季度食材涨价"）
    
    boss_final_price DECIMAL(15,2) NOT NULL,             -- 老板最终定价（必填）
    boss_decision_reason TEXT NOT NULL,                  -- 决策理由（强制填写）
    boss_decision_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 与系统建议的差异分析（自动计算）
    deviation_from_system DECIMAL(5,4),  -- (boss_final - system_suggested_optimal) / system_suggested_optimal
    deviation_reason_category VARCHAR(50), -- 差异原因分类：competition_intelligence / profit_reserve / relationship_leverage / other
    
    -- 招标文件约束检查
    budget_limit DECIMAL(15,2),      -- 预算价/限价（从招标文件解析）
    is_under_limit BOOLEAN,           -- 是否低于限价
    limit_violation_warning TEXT,   -- 超限警告（如：超限价5%，可能废标）
    
    -- 博弈模型输出（JSON存储详细计算过程）
    game_theory_analysis JSONB,  -- {
                                --   "price_scenarios": [
                                --     {"price": 950000, "win_prob": 0.8, "expected_profit": 19000, "score": 95},
                                --     {"price": 980000, "win_prob": 0.6, "expected_profit": 29400, "score": 98}
                                --   ],
                                --   "competitor_prediction": ["A公司可能报92-95万", "B公司可能报96-98万"],
                                --   "price_score_calculation": "基于招标文件：价格分=基准价/投标价*100"
                                -- }
    
    status VARCHAR(20) DEFAULT 'decided',  -- decided / revised / confirmed_in_bid
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 价格历史库（用于训练博弈模型，从11份文件+后续爬取数据积累）
    CREATE TABLE price_history (
    id SERIAL PRIMARY KEY,
    project_type VARCHAR(100),       -- 学校食堂/政府物业/医院
    region VARCHAR(100),             -- 地区（用于区域价格差异）
    budget_amount DECIMAL(15,2),     -- 预算价
    our_cost DECIMAL(15,2),          -- 我们的成本（脱敏存储）
    our_bid_price DECIMAL(15,2),     -- 我们的报价
    winning_price DECIMAL(15,2),     -- 中标价（公开数据）
    winning_unit VARCHAR(255),       -- 中标单位（竞争对手）
    discount_rate DECIMAL(5,4),      -- 下浮率（winning_price / budget_amount）
    bid_date DATE,                   -- 投标日期
    is_our_win BOOLEAN,              -- 是否我们中标
    data_source VARCHAR(50)          -- 内部数据 / 爬虫公开数据
    );

三、核心算法逻辑（Python 伪代码）
3.1 博弈定价模型（冷启动版）

    class PricingGameTheoryModel:
    def __init__(self, project_id: int):
        self.project = db.get_project(project_id)
        self.tender = db.get_tender_document(project_id)
        self.cost = db.get_latest_confirmed_cost(project_id)
        
    def calculate_win_probability(self, proposed_price: float) -> dict:
        """
        计算特定报价下的中标概率
        冷启动策略：规则+启发式，非ML（数据不足时）
        """
        budget = self.tender.budget_amount
        price_score_weight = self.tender.price_score_weight  # 价格分权重（如30%）
        
        # 1. 计算价格分（基于常见政府采购评分规则）
        # 规则A：最低价满分，其他按比例扣分
        # 规则B：基准价法（去掉高低后的平均价作为基准）
        # 这里实现规则A（可配置）
        assumed_lowest_competitor = budget * 0.85  # 假设最低竞争对手报85%预算（调研数据）
        if proposed_price <= assumed_lowest_competitor:
            price_score = 100
        else:
            price_score = (assumed_lowest_competitor / proposed_price) * 100
        
        # 2. 技术商务分估算（基于Week 3技术标质量）
        tech_quality_score = self.estimate_tech_score()  # 从tech_proposal_tasks获取
        business_score = 90 if self.project.relationship_index > 50 else 75  # 有关系商务分高
        
        # 3. 综合得分计算
        total_score = (
            tech_quality_score * (1 - price_score_weight - 0.3) +  # 技术分权重
            business_score * 0.3 +  # 商务分固定30%（假设）
            price_score * price_score_weight  # 价格分
        )
        
        # 4. 概率映射（得分→概率，使用Sigmoid或线性分段）
        # 假设：85分以上大概率中标，70分以下小概率
        if total_score >= 90:
            win_prob = 0.85
        elif total_score >= 80:
            win_prob = 0.65
        elif total_score >= 70:
            win_prob = 0.40
        else:
            win_prob = 0.15
            
        # 5. 关系调整（有关系项目概率保底）
        if self.project.relationship_index >= 80:
            win_prob = max(win_prob, 0.75)  # 有关系项目至少75%概率
        
        return {
            'proposed_price': proposed_price,
            'price_score': price_score,
            'tech_business_score': tech_quality_score * (1 - price_score_weight) + business_score * 0.3,
            'total_score': total_score,
            'win_probability': win_prob,
            'expected_profit': (proposed_price - self.cost.total_cost) * win_prob,  # 期望收益=利润*概率
            'profit_margin': (proposed_price - self.cost.total_cost) / proposed_price
        }
    
    def generate_price_scenarios(self) -> list:
        """
        生成多个价格场景供决策参考（A/B/C场景）
        """
        cost = self.cost.total_cost
        scenarios = []
        
        # 场景A：激进策略（薄利多销）
        price_a = cost * 1.03  # 3%利润
        result_a = self.calculate_win_probability(price_a)
        scenarios.append({
            'scenario': 'aggressive',
            'price': price_a,
            'label': '激进策略（成本+3%）',
            'win_prob': result_a['win_probability'],
            'profit': result_a['proposed_price'] - cost,
            'expected_value': result_a['expected_profit'],
            'risk_level': 'low' if result_a['win_probability'] > 0.7 else 'medium'
        })
        
        # 场景B：平衡策略（常规利润）
        price_b = cost * 1.08  # 8%利润
        result_b = self.calculate_win_probability(price_b)
        scenarios.append({
            'scenario': 'balanced',
            'price': price_b,
            'label': '平衡策略（成本+8%）',
            'win_prob': result_b['win_probability'],
            'profit': result_b['proposed_price'] - cost,
            'expected_value': result_b['expected_profit'],
            'risk_level': 'medium'
        })
        
        # 场景C：保守策略（高利润低中标率）
        price_c = cost * 1.15  # 15%利润
        result_c = self.calculate_win_probability(price_c)
        scenarios.append({
            'scenario': 'conservative',
            'price': price_c,
            'label': '保守策略（成本+15%）',
            'win_prob': result_c['win_probability'],
            'profit': result_c['proposed_price'] - cost,
            'expected_value': result_c['expected_profit'],
            'risk_level': 'high'
        })
        
        # 推荐最优（期望收益最大化）
        optimal = max(scenarios, key=lambda x: x['expected_value'])
        optimal['is_recommended'] = True
        
        return scenarios
    
    def estimate_tech_score(self) -> float:
        """
        从技术标生成任务获取预估技术分
        """
        tech_task = db.query("""
            SELECT generated_content->>'optimization_level' as opt_level
            FROM tech_proposal_tasks 
            WHERE project_id = %s AND status = 'confirmed'
            ORDER BY created_at DESC LIMIT 1
        """, self.project.id)
        
        if tech_task and tech_task.opt_level == 'high':
            return 85  # 极致优化预估85分
        return 75  # 普通水平预估75分

3.2 成本测算引擎

    class CostEstimationEngine:
    """
    基于历史项目数据，智能测算新项目成本
    """
    def estimate_from_history(self, new_project: dict) -> dict:
        """
        从历史11份文件+后续数据，寻找相似项目估算成本
        """
        # 相似度匹配维度：项目类型、规模（预算）、地区、服务范围
        similar_projects = db.query("""
            SELECT ph.our_cost, ph.budget_amount, ph.our_bid_price
            FROM price_history ph
            WHERE ph.project_type = %s 
            AND ph.region = %s
            AND ABS(ph.budget_amount - %s) / %s < 0.2  -- 预算差异<20%
            ORDER BY ph.bid_date DESC
            LIMIT 5
        """, new_project['type'], new_project['region'], new_project['budget'], new_project['budget'])
        
        if similar_projects:
            # 基于历史平均成本+通胀调整
            avg_cost = sum(p.our_cost for p in similar_projects) / len(similar_projects)
            inflation_factor = 1.05  # 假设年通胀5%
            years_diff = (datetime.now() - similar_projects[0].bid_date).days / 365
            
            estimated_base = avg_cost * (inflation_factor ** years_diff)
            
            return {
                'estimated_total': estimated_base,
                'confidence': 'medium' if len(similar_projects) >= 3 else 'low',
                'based_on': f"{len(similar_projects)}个历史相似项目",
                'breakdown': self.breakdown_cost(estimated_base, new_project)
            }
        else:
            # 无历史数据：基于预算比例回推（行业经验：食材配送成本约占预算70-80%）
            estimated_total = new_project['budget'] * 0.75
            return {
                'estimated_total': estimated_total,
                'confidence': 'low',
                'based_on': '行业经验比例（预算75%）',
                'breakdown': self.breakdown_cost(estimated_total, new_project),
                'warning': '无相似历史项目，建议人工仔细核算'
            }
    
    def breakdown_cost(self, total: float, project: dict) -> dict:
        """
        成本拆解为明细（供财务审核调整）
        """
        # 行业经验比例（可根据你的实际业务调整）
        return {
            'food_cost': total * 0.55,        # 食材占55%
            'labor_cost': total * 0.25,       # 人工占25%
            'logistics_cost': total * 0.12,   # 物流占12%
            'management_cost': total * 0.08   # 管理占8%
        }

四、API 接口定义（FastAPI）
4.1 成本录入 API

#POST /api/projects/{project_id}/cost-estimates
class CostEstimateCreate(BaseModel):
    food_cost: float
    logistics_cost: float
    labor_cost: float
    management_cost: float
    other_cost: float = 0
    estimate_reason: str  # 必填：测算依据

class CostEstimateResponse(BaseModel):
    id: int
    version_number: int
    total_cost: float
    breakdown: dict
    estimated_by: str
    is_confirmed: bool

#确认成本版本（锁定为定价基准）
#POST /api/cost-estimates/{estimate_id}/confirm

4.2 博弈定价计算 API
#POST /api/projects/{project_id}/pricing-calculations
#Request: 无（基于已确认成本自动计算）
#Response:
class PricingCalculationResponse(BaseModel):
    project_id: int
    cost_base: float
    budget_limit: float  # 招标文件限价
    scenarios: List[PriceScenario]  # A/B/C三种策略
    optimal_recommendation: PriceScenario  # 系统推荐
    price_score_explanation: str  # 价格分计算规则说明
    
class PriceScenario(BaseModel):
    scenario: str  # aggressive/balanced/conservative
    price: float
    win_probability: float
    profit_amount: float
    expected_value: float  # 期望收益 = 利润*概率
    risk_level: str
    is_recommended: bool = False

#获取定价决策界面数据
#GET /api/projects/{project_id}/pricing-dashboard
#返回：成本信息 + 场景分析 + 历史对标 + 限价检查

4.3 定价决策提交 API
#POST /api/projects/{project_id}/pricing-decisions
class PricingDecisionCreate(BaseModel):
    boss_final_price: float
    boss_decision_reason: str  # 必填
    deviation_reason_category: str  # competition_intelligence/profit_reserve/relationship_leverage/other
    finance_suggested_price: Optional[float] = None  # 财务建议（可选）
    finance_suggestion_reason: Optional[str] = None

#校验规则：
#1. boss_final_price 必须 > cost_base（否则报错"亏损定价不可提交"）
#2. 如果 boss_final_price > budget_limit，警告"超限价可能废标"，需二次确认参数 confirm_override=true
#3. 如果 |price - system_suggested_optimal| / system_suggested_optimal > 0.05，强制要求 boss_decision_reason 长度>10

#Response: 决策记录ID + 下一步操作（进入形式审查）

4.4 版本历史 API
#GET /api/projects/{project_id}/pricing-history
#返回该项目的所有定价决策历史（支持老板修改后追溯）

五、前端界面设计（关键页面）
5.1 定价决策驾驶舱（Pricing Dashboard）
布局结构：

┌─────────────────────────────────────────────────────────────────┐
│ 项目：XX学校食堂配送    预算限价：150万    状态：技术标已确认         │
├─────────────────────────────────────────────────────────────────┤
│ 左侧：成本基线面板        │  右侧：博弈分析面板                     │
│ ├─ 食材成本：82.5万      │  ├─ 价格分计算规则：最低价法（30%权重）   │
│ ├─ 人工成本：37.5万      │  ├─ 预估竞争对手低价：127.5万（85%预算） │
│ ├─ 物流成本：18万        │  ├─ 我们的成本线：135万                   │
│ ├─ 管理成本：12万        │  └─ 最低可报价：137.7万（+2%）           │
│ └─ 总成本：150万         │                                         │
│ [查看成本明细→]          │                                         │
├─────────────────────────────────────────────────────────────────┤
│ 三种报价策略对比（博弈矩阵）                                      │
│ ┌─────────────┬──────────┬──────────┬──────────┬──────────────┐ │
│ │   策略      │  报价    │ 中标概率 │  利润    │  期望收益    │ │
│ ├─────────────┼──────────┼──────────┼──────────┼──────────────┤ │
│ │ 激进     │ 137.7万  │   85%    │  2.7万   │  2.30万      │ │ ← 推荐（期望收益最高）
│ │ 平衡     │ 145万    │   60%    │  10万    │  6.00万      │ │
│ │ 保守     │ 155万    │   25%    │  20万    │  5.00万      │ │ ← 超限价，警告！
│ └─────────────┴──────────┴──────────┴──────────┴──────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ 历史中标对标（基于爬取/内部数据）                                 │
│ • 类似项目（150万预算学校食堂）：平均中标价142万（94.7%预算）       │
│ • 主要竞争对手"A公司"近期报价区间：138-145万                      │
├─────────────────────────────────────────────────────────────────┤
│ 决策输入区                                                        │
│ 财务建议价：____万（可选）    理由：___________                   │
│                                                                 │
│ [最终定价]*：____万（必填）                                           │
│ [定价差异原因]*（如与系统推荐差异>5%必填）：                           │
│ ○ 竞争情报（知悉对手报低价）                                          │
│ ○ 利润预留（需保证XX利润）                                            │
│ ○ 关系利用（有关系可报高）                                            │
│ ○ 其他：__________                                                    │
│                                                                 │
│ [确认定价并生成商务标]                                               │
└─────────────────────────────────────────────────────────────────┘

六、关键业务校验规则（代码必须实现）
成本倒挂拦截：如果 total_cost > budget_limit * 0.95，系统警告"成本接近限价，利润空间极小"，要求确认"是否继续"
亏损定价拦截：如果 boss_final_price < total_cost * 1.01（低于1%利润），禁止提交，提示"亏损定价不可接受"
超限强制确认：如果 boss_final_price > budget_limit，弹出二次确认框："报价超限价，可能直接废标，是否确认？"
差异原因强制：如果 abs(boss_final_price - system_suggested_optimal) / system_suggested_optimal > 0.05 且 len(boss_decision_reason) < 10，API返回400错误"请详细说明定价差异原因（至少10字）"
七、冷启动数据处理策略（必读）
由于目前只有11份历史文件，系统需要支持无历史数据时的优雅降级：
成本估算：无相似项目时，使用"预算*75%"作为估算基准，并标记confidence: low，提示用户"请人工仔细核算"
博弈模型：无历史中标价数据时，使用"预算*85%"作为假设竞争对手低价，并提示"基于行业假设，实际可能偏差较大"
数据积累：每次投标后（无论中标与否），强制要求录入actual_cost和winning_price，逐步填充price_history表
八、交付标准（验收 checklist）
[ ] 成本录入支持版本控制（修改后version_number递增）
[ ] 博弈定价API返回3种场景（激进/平衡/保守），包含期望收益计算
[ ] 老板定价界面显示"限价检查"，超限价时红色警告
[ ] 定价差异>5%时强制填写原因，并记录到deviation_reason_category
[ ] 确认定价后，商务标中的报价部分自动更新（技术标Week 3已生成，Week 4生成商务标或更新报价字段）
[ ] 形式审查前置检查：在生成最终标书前检查报价合规性

请按以下优先级开发：
Day 1-2：数据库表 + 成本录入API + 基础前端界面
Day 3-4：博弈定价算法（冷启动版）+ 定价决策API + 博弈矩阵前端
Day 5：版本控制逻辑 + 与Week 3技术标的集成（回填价格）+ 校验规则拦截
注意处理浮点数精度（金额用Decimal），以及并发控制（多人同时操作成本时的版本冲突处理）。
如有任何技术实现疑问，请基于文档中的伪代码逻辑进行合理工程取舍，保持业务逻辑正确优先。