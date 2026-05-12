文档元信息
开发周期：Week 7（5个工作日）
依赖前提：Week 1-6 已完成（全功能闭环）
核心业务目标：实现多投标并行管理、数据决策看板、系统管理后台、封装输出精细化
关键价值：从"能用"到"好用"，支持业务规模化扩张
一、业务逻辑架构（必读）
1.1 Week 7 核心场景
场景A：多项目并行管理
公司同时投 5 个标，时间冲突（3 个下周一开标，2 个下周三开标）
标书专员资源分配（一人同时跟进多个项目）
老板需要全局视图（哪些在定价阶段、哪些在形式审查、哪些即将过期）
场景B：数据驱动决策
月度复盘：中标率趋势、有内幕 vs 无内幕胜率对比、各地区胜率热力图
知识库健康度：哪些标准资质经常缺失、哪些技术方案段落最受欢迎
财务分析：投入产出比（投标成本 vs 中标金额）
场景C：系统管理
新增学校/政府单位到业主画像库
维护标准资质库（新增证书类型、更新有效期规则）
用户权限调整（新增标书专员、财务账号）
场景D：物理封装辅助
生成打印优化版 PDF（双面打印、页码连续、封装标签打印页）
封装清单生成（带二维码，手机扫描可查看电子版核对清单）
二、数据库表设计（SQL）
sql
复制
-- 多项目资源调度表（解决并行冲突）
CREATE TABLE project_schedules (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    
    -- 关键时间节点（从招标文件解析 + 人工调整）
    milestone_dates JSONB NOT NULL, -- {
                                    --   "upload_deadline": "2026-04-01",
                                    --   "pricing_decision_by": "2026-04-03", 
                                    --   "formal_review_by": "2026-04-05",
                                    --   "print_bind_by": "2026-04-06",
                                    --   "submit_by": "2026-04-07 09:00"
                                    -- }
    
    -- 资源分配
    assigned_specialist_id INTEGER REFERENCES users(id),
    assigned_finance_id INTEGER REFERENCES users(id),  -- 如涉及复杂定价
    
    -- 冲突检测
    workload_score INTEGER,  -- 工作量评分（基于项目规模、复杂度）
    conflict_flags JSONB,      -- ["与项目123时间冲突", "专员张三 overloaded"]
    
    -- 提醒设置
    reminder_settings JSONB,   -- {"1_day_before": true, "4_hours_before": true}
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 数据看板指标表（预计算，提升查询性能）
    CREATE TABLE dashboard_metrics (
    id SERIAL PRIMARY KEY,
    metric_date DATE,          -- 统计日期
    metric_type VARCHAR(50),   -- win_rate / cost_efficiency / knowledge_health
    
    -- 中标率指标
    total_bids INTEGER,
    won_bids INTEGER,
    win_rate DECIMAL(5,2),           -- 总中标率
    win_rate_with_relationship DECIMAL(5,2),  -- 有内幕中标率
    win_rate_without_relationship DECIMAL(5,2), -- 无内幕中标率
    
    -- 财务指标
    total_bid_amount DECIMAL(15,2),    -- 投标总额
    total_won_amount DECIMAL(15,2),    -- 中标总额
    avg_cost_per_bid DECIMAL(10,2),    -- 平均投标成本（人力+制作）
    roi_ratio DECIMAL(5,2),            -- 投入产出比
    
    -- 效率指标
    avg_time_to_prepare DECIMAL(5,1),  -- 平均准备天数（从上传到提交）
    formal_review_pass_rate DECIMAL(5,2), -- 形式审查一次通过率
    
    -- 知识库指标
    knowledge_chunks_total INTEGER,
    knowledge_chunks_deprecated INTEGER,
    avg_chunk_quality DECIMAL(5,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(metric_date, metric_type)
    );

    -- 系统配置表（标准库维护）
    CREATE TABLE system_configurations (
    id SERIAL PRIMARY KEY,
    config_category VARCHAR(50),   -- 'standard_certs' / 'owner_profiles' / 'pricing_rules'
    config_key VARCHAR(100),
    config_value JSONB,
    updated_by INTEGER REFERENCES users(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 封装打印任务表（物理标书管理）
    CREATE TABLE packaging_tasks (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    
    -- 打印设置
    print_settings JSONB,      -- {"copies_original": 1, "copies_copy": 4, "double_sided": true, "color_pages": [1,2,3]}
    binding_type VARCHAR(50),  -- '胶装' / '线装' / '骑马钉'
    
    -- 封装清单（生成打印页）
    packaging_checklist JSONB, -- 带勾选框的清单
    seal_labels_generated BOOLEAN DEFAULT FALSE, -- 密封标签是否已生成PDF
    
    -- 物流/递交
    delivery_method VARCHAR(50), -- 'self_deliver' / 'courier' / 'electronical'
    delivery_tracking_no VARCHAR(100),
    
    status VARCHAR(20) DEFAULT 'pending', -- pending / printed / packaged / delivered
    completed_by INTEGER REFERENCES users(id),
    completed_at TIMESTAMP
    );

三、核心功能模块（开发指令）

3.1 多项目协同管理（Project Orchestration）

    class ProjectOrchestration:
    def detect_conflicts(self, specialist_id: int, date_range: tuple) -> list:
        """
        检测资源冲突（专员工作负载、时间重叠）
        """
        projects = db.query("""
            SELECT p.*, ps.milestone_dates->>'submit_by' as submit_date
            FROM projects p
            JOIN project_schedules ps ON ps.project_id = p.id
            WHERE ps.assigned_specialist_id = %s
            AND ps.milestone_dates->>'submit_by' BETWEEN %s AND %s
            AND p.status NOT IN ('abandoned', 'completed')
        """, specialist_id, date_range[0], date_range[1])
        
        conflicts = []
        
        # 检查同一时间多个项目需形式审查
        review_dates = [p for p in projects if p['milestone_dates'].get('formal_review_by')]
        for i, proj1 in enumerate(review_dates):
            for proj2 in review_dates[i+1:]:
                if abs((proj1['formal_review_date'] - proj2['formal_review_date']).days) < 1:
                    conflicts.append({
                        'type': 'time_collision',
                        'severity': 'high',
                        'project_1': proj1['id'],
                        'project_2': proj2['id'],
                        'collision_date': proj1['formal_review_date'],
                        'suggestion': '建议调整项目2的形式审查至前一天，或分配其他专员'
                    })
        
        # 检查工作量过载（假设一个专员同时最多3个项目）
        if len(projects) > 3:
            conflicts.append({
                'type': 'workload_overload',
                'severity': 'medium',
                'specialist_id': specialist_id,
                'active_projects': len(projects),
                'suggestion': '该专员当前负责4个项目，建议调配资源或延期低优先级项目'
            })
        
        return conflicts
    
    def generate_calendar_view(self, user_id: int, role: str, month: int) -> dict:
        """
        生成日历视图（老板看全公司，专员看自己，财务看待定价）
        """
        if role == 'boss':
            projects = db.query("SELECT * FROM projects WHERE status != 'abandoned'")
        elif role == 'specialist':
            projects = db.query("""
                SELECT p.* FROM projects p
                JOIN project_schedules ps ON ps.project_id = p.id
                WHERE ps.assigned_specialist_id = %s
            """, user_id)
        elif role == 'finance':
            projects = db.query("""
                SELECT p.* FROM projects p
                JOIN bid_evaluation_reports ber ON ber.project_id = p.id
                WHERE ber.recommendation = 'worth_bidding'
                AND p.status = 'awaiting_pricing'
            """)
        
        # 转换为日历事件
        events = []
        for p in projects:
            schedule = db.get_project_schedule(p['id'])
            if schedule:
                for milestone, date in schedule['milestone_dates'].items():
                    events.append({
                        'title': f"{p['project_name']} - {milestone}",
                        'date': date,
                        'project_id': p['id'],
                        'status': p['status'],
                        'urgency': self.calculate_urgency(date)
                    })
        
        return {
            'month': month,
            'events': events,
            'conflicts': self.detect_all_conflicts(month)
        }

3.2 数据看板与 BI（Dashboard & Analytics）

    class DashboardEngine:
    def calculate_daily_metrics(self, date: datetime) -> dict:
        """
        每日凌晨计算昨日指标（可设为定时任务）
        """
        # 中标率统计（区分有内幕/无内幕）
        outcomes = db.query("""
            SELECT 
                SUM(CASE WHEN outcome_status = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN relationship_flag = true AND outcome_status = 'win' THEN 1 ELSE 0 END) as wins_with_rel,
                SUM(CASE WHEN relationship_flag = false AND outcome_status = 'win' THEN 1 ELSE 0 END) as wins_without_rel,
                COUNT(*) as total
            FROM bid_outcomes
            WHERE DATE(created_at) = %s
        """, date)
        
        # 知识库健康度
        knowledge_stats = db.query("""
            SELECT 
                COUNT(*) as total_chunks,
                SUM(CASE WHEN is_deprecated = true THEN 1 ELSE 0 END) as deprecated,
                AVG(quality_score) as avg_quality
            FROM knowledge_chunks
        """)
        
        metrics = {
            'metric_date': date,
            'metric_type': 'daily_summary',
            'win_rate': outcomes['wins'] / outcomes['total'] if outcomes['total'] > 0 else 0,
            'win_rate_with_relationship': outcomes['wins_with_rel'] / (outcomes['wins_with_rel'] + outcomes['losses_with_rel']),
            'win_rate_without_relationship': outcomes['wins_without_rel'] / (outcomes['wins_without_rel'] + outcomes['losses_without_rel']),
            'knowledge_health': {
                'total': knowledge_stats['total_chunks'],
                'deprecated_ratio': knowledge_stats['deprecated'] / knowledge_stats['total_chunks'],
                'avg_quality': knowledge_stats['avg_quality']
            }
        }
        
        db.insert('dashboard_metrics', metrics)
        return metrics
    
    def get_boss_kpi_dashboard(self) -> dict:
        """
        老板首页KPI看板（实时查询）
        """
        current_month = datetime.now().month
        
        return {
            'this_month': {
                'active_bids': db.count("projects WHERE status IN ('approved_by_specialist', 'generating_documents', 'awaiting_pricing')"),
                'pending_decisions': db.count("projects WHERE status = 'awaiting_pricing'"),  # 等你定价
                'upcoming_deadlines': db.query("SELECT * FROM projects WHERE bid_open_date <= NOW() + INTERVAL '7 days'"),
                'win_rate_trend': self.get_trend_chart_data('win_rate', 6)  # 近6个月趋势
            },
            'financial': {
                'total_bid_amount_this_month': db.sum("final_bid_price FROM pricing_decisions WHERE MONTH(created_at) = %s", current_month),
                'estimated_cost_this_month': db.sum("cost_base FROM pricing_decisions WHERE MONTH(created_at) = %s", current_month),
                'roi_forecast': self.calculate_roi_forecast()
            },
            'risks': {
                'high_risk_projects': db.query("""
                    SELECT p.*, ber.overall_win_probability 
                    FROM projects p
                    JOIN bid_evaluation_reports ber ON ber.project_id = p.id
                    WHERE ber.overall_win_probability < 0.3
                    AND p.status != 'abandoned'
                """),  # 中标概率低于30%但未放弃的项目
                'overdue_reviews': db.query("SELECT * FROM formal_review_items WHERE specialist_status = 'pending' AND created_at < NOW() - INTERVAL '3 days'")
            }
        }

3.3 封装输出精细化（Packaging & Delivery）

    class PackagingEngine:
    def generate_print_optimized_pdf(self, project_id: int) -> str:
        """
        生成打印优化版PDF（解决标书打印的物理问题）
        """
        # 获取Week 5生成的Word
        word_path = db.get_final_document_path(project_id)
        
        # 转换为PDF（如需要）
        pdf_path = convert_word_to_pdf(word_path)
        
        # 优化设置：
        # 1. 插入分隔页（技术标/商务标/资格标分册标识）
        # 2. 生成页眉页脚（项目名称、页码、正本/副本标记）
        # 3. 彩色页标记（封面、评分索引用彩色，其余黑白节省成本）
        
        doc = fitz.open(pdf_path)
        
        # 添加页眉
        for page_num in range(len(doc)):
            page = doc[page_num]
            header = f"{project_name} - 第{page_num+1}页"
            page.insert_text((50, 30), header, fontsize=9, color=(0.5, 0.5, 0.5))
            
            # 正本/副本水印（根据设置）
            if page_num < original_copy_page_count:
                page.insert_text((page.rect.width/2, page.rect.height/2), "正本", 
                               fontsize=40, color=(0.9, 0.9, 0.9), rotate=45)
        
        output_path = f"/output/print_optimized_{project_id}.pdf"
        doc.save(output_path)
        return output_path
    
    def generate_seal_labels(self, project_id: int) -> str:
        """
        生成密封标签打印页（A4纸打印后裁剪粘贴）
        """
        project = db.get_project(project_id)
        
        labels = [
            f"技术标正本\n项目名称：{project['name']}\n投标人：{company_name}\n开标时间前不得启封",
            f"技术标副本（1）\n项目名称：{project['name']}\n开标时间前不得启封",
            f"商务标正本\n项目名称：{project['name']}\n开标时间前不得启封",
            # ... 根据招标文件要求动态生成
        ]
        
        # 生成可打印PDF（每页4个标签，带裁剪线）
        return generate_label_pdf(labels)
    
    def generate_qr_packaging_guide(self, project_id: int) -> dict:
        """
        生成带二维码的封装指南（扫码查看电子版核对清单）
        """
        checklist = db.get_packaging_checklist(project_id)
        
        # 生成唯一URL
        qr_url = f"https://your-system.com/packaging-check/{project_id}?token={secure_token}"
        
        # 生成二维码图片
        qr_code = generate_qr_code(qr_url)
        
        # 生成PDF（一页，包含清单+二维码）
        guide_pdf = create_packaging_guide_pdf(checklist, qr_code)
        
        return {
            'qr_code_path': qr_code,
            'guide_pdf_path': guide_pdf,
            'mobile_url': qr_url  # 手机扫码后打开核对页面（可勾选）
        }

3.4 系统管理后台（Administration）

    class SystemAdmin:
    def maintain_standard_certs(self, action: str, data: dict):
        """
        维护标准资质库（Week 1预生成的数据，现在提供管理界面）
        """
        if action == 'add':
            # 新增证书类型
            db.insert('standard_certifications', {
                'cert_code': data['code'],
                'cert_full_name': data['name'],
                'required_keywords': json.dumps(data['keywords']),
                'exclude_keywords': json.dumps(data['excludes']),
                'cert_number_pattern': data['pattern']
            })
        elif action == 'update':
            # 更新（如有效期规则变化）
            db.update('standard_certifications', {
                'id': data['id'],
                'validity_years': data['validity']
            })
        elif action == 'deprecate':
            # 标记废弃（如某资质已取消全国性认证）
            db.update('standard_certifications', {
                'id': data['id'],
                'is_active': False
            })
    
    def maintain_owner_profiles(self, owner_data: dict):
        """
        维护业主画像库（新增合作单位、更新关系等级）
        """
        db.upsert('owner_profiles', {
            'owner_name': owner_data['name'],
            'cooperation_count': owner_data['count'],
            'relationship_level': owner_data['level'],
            'preferred_styles': json.dumps(owner_data['styles'])
        }, unique_key='owner_name')
    
    def user_management(self, user_data: dict):
        """
        用户管理（新增专员、财务账号，调整权限）
        """
        if user_data['role'] == 'specialist':
            permissions = ['upload', 'parse', 'evaluate', 'approve_worthy', 'edit_tech', 'formal_review']
        elif user_data['role'] == 'finance':
            permissions = ['view_cost', 'input_cost', 'suggest_price', 'view_dashboard']
        elif user_data['role'] == 'boss':
            permissions = ['all']  # 全部权限
        
        db.insert('users', {
            'username': user_data['username'],
            'role': user_data['role'],
            'permissions': json.dumps(permissions),
            'is_active': True
        })

四、API 接口定义（关键新增）
#多项目日历 API
#GET /api/calendar?month=2026-04&role=boss
#Response: 事件数组 + 冲突标记

#数据看板 API
#GET /api/dashboard/kpi
#Response: 中标率、财务指标、风险项目列表

#封装任务 API
#POST /api/projects/{id}/packaging/initiate
#Request: {print_settings: {...}, binding_type: "胶装"}
#Response: {print_optimized_pdf_url, seal_labels_pdf_url, qr_guide_url}

#系统管理 API（需老板权限）
#POST /api/admin/standard-certs  # 维护标准资质库
#POST /api/admin/owner-profiles  # 维护业主画像
#GET /api/admin/knowledge-health # 知识库健康度诊断（冷门知识清理建议）

#冲突检测 API
#GET /api/resource-conflicts?specialist_id=123&week=2026-W15
#Response: 冲突列表 + 调整建议

五、前端界面设计（关键页面）
5.1 老板驾驶舱（Dashboard）
┌─────────────────────────────────────────────────────────────────────┐
│ 本月概览（2026年4月）                                                │
├──────────────────┬──────────────────┬─────────────────────────────────┤
│    中标率       │    财务        │    风险预警                   │
│  总：45%         │  投标额：500万   │  3个项目低于30%胜率未放弃       │
│  有内幕：80%     │  预估成本：420万 │  2个项目形式审查超期            │
│  无内幕：25%     │  ROI：1.19      │  1个项目资质即将过期            │
├──────────────────┴──────────────────┴─────────────────────────────────┤
│ 项目日历（未来14天）                                                  │
│ ┌─────┬───────────────────────────────────────────────────────────┐ │
│ │ 周一│ 🔴 09:00 XX中学开标（形式审查中，紧急）                      │ │
│ │     │ 🟡 14:00 XX政府定价决策（待你审批）                        │ │
│ │ 周二│ 🟢 XX小学技术标编辑中（正常）                              │ │
│ │ 周三│ 🔴 09:00 XX医院开标（资质有问题，建议放弃）                 │ │
│ └─────┴───────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│ 知识库健康度：85%（45个冷门段落待清理，建议本周Review）               │
│ 本周中标DNA新增：3个  |  废标陷阱新增：1个（签字日期逻辑）            │
└─────────────────────────────────────────────────────────────────────┘

5.2 封装打印工作台

项目：XX学校食堂配送（已形式审查通过）

打印设置：
┌─────────────────────────────────────────────────────────┐
│ 份数设置：                                               │
│ 正本：1份  [+] [-]      副本：4份  [+] [-]               │
│                                                         │
│ 打印选项：                                               │
│ ☑ 双面打印（节省纸张）                                   │
│ ☑ 封面彩色（技术标封面用彩色纸）                          │
│ ☐ 插页分隔（技术标/商务标之间插彩页分隔）                  │
│                                                         │
│ 页码范围：                                               │
│ • 技术标：1-45页（彩色打印：1-3页封面索引）                │
│ • 商务标：46-52页（黑白）                                │
│ • 资格标：53-78页（黑白，证书复印件）                     │
├─────────────────────────────────────────────────────────┤
│ 封装标签生成：                                           │
│ [生成密封标签PDF（A4打印裁剪）]                           │
│ [生成封装核对清单（带二维码）]                            │
│ [生成递交授权书（如委托他人递交）]                        │
└─────────────────────────────────────────────────────────┘

[开始打印任务]  [下载完整标书包]

六、关键业务规则（Week 7 特化）
并发限制：一个标书专员最多同时负责 3 个"进行中"项目（形式审查前），超过时系统警告并建议延期或增派人员。
自动提醒：开标前 24 小时、4 小时自动发送提醒（短信/邮件/系统内），如形式审查未完成则标记为红色紧急。
数据归档：中标/废标项目 30 天后自动归档（文件移入冷存储），但知识库数据保留。
权限隔离：财务只能看到成本相关数据，不能下载完整标书文件；专员不能修改定价决策。
七、交付标准（Week 7 最终验收）
[ ] 老板首页显示 KPI 看板（中标率、财务、风险预警）
[ ] 日历视图显示多项目时间线，红色标记冲突
[ ] 封装标签生成 PDF（可打印裁剪粘贴）
[ ] 系统管理后台可新增/编辑标准资质、业主画像
[ ] 知识库健康度诊断报告（显示冷门知识、推荐清理）
[ ] 完整系统部署文档（Docker Compose 生产环境配置）

Week 7 是项目的工程化与规模化阶段，重点是：
并发处理：多项目并行时的资源冲突检测
数据可视化：让老板一眼看清业务全局
物理交付：从数字文件到纸质标书的最后一公里（打印优化、封装辅助）
系统治理：标准库维护、权限管理、数据清理
至此，Week 1-7 完成从 0 到 1 的 MVP 全功能开发，可直接投入生产使用。后续迭代建议（Week 8+）：竞争对手爬虫自动化、AI 智能定价模型训练、移动端 App 等。