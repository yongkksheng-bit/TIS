Week 5 开发文档：形式审查与最终输出系统（FRCS + Output Engine）
文档元信息
开发周期：Week 5（5个工作日）
依赖前提：Week 1-4 已完成（OCR基础、资质匹配、技术标、定价）
核心业务目标：实现形式审查（列表+PDF高亮）→ 人工确认/修正 → 强制拦截 → 最终Word标书生成
关键约束：审查不通过100%拦截生成按钮；支持人工补充系统未识别的风险
一、业务逻辑架构（必读）
1.1 形式审查 Workflow（强制拦截机制）

[定价决策完成] 
    ↓
[形式审查启动] ← 自动对比：投标文件 vs 招标文件要求
    ├─ 资质有效性审查（证书有效期覆盖开标日？）
    ├─ 签字盖章审查（正本要求 vs 实际PDF页数）
    ├─ 密封要求审查（招标文件密封条款解析）
    ├─ 报价合规审查（Week 4定价 vs 限价检查）
    ├─ 技术标完整性审查（Week 3生成内容是否缺失）
    ↓
[审查结果呈现] ← 双视图：列表打钩 + PDF高亮圈注
    ├─ 绿色：通过（系统自动确认）
    ├─ 黄色：警告（需人工确认）
    └─ 红色：致命（必须修正才能继续）
    ↓
[人工确认环节] ← 标书专员操作
    ├─ 点击【确认通过】（认可系统判断）
    ├─ 点击【补充说明】（系统漏检，人工补充证据）
    ├─ 点击【删除此项】（系统误报，标记为误报原因）
    └─ 点击【全局补充】（新增系统未列出的特殊风险）
    ↓
[强制拦截检查]
    IF 存在未处理的红色致命项 THEN
        【生成最终标书】按钮 = 禁用（灰色）
        提示："存在致命风险未处理，请修正后重试"
    ELSE IF 存在未确认的黄色警告项 THEN
        【生成最终标书】按钮 = 可用但需二次确认
        提示："存在警告项未确认，是否继续？"
    ELSE
        【生成最终标书】按钮 = 启用（绿色）
    ↓
[最终标书生成]
    ├─ 合并技术标（Week 3）+ 商务标报价（Week 4）
    ├─ 插入业绩案例扫描件（数据库路径引用）
    ├─ 生成评分点索引页（Week 3）
    ├─ 生成封装指南页（密封签、封装清单）
    └─ 输出：完整Word文档（分册或合并）

1.2 关键业务规则（硬性约束）
规则1：检查项动态生成
结构化检查项：从 tender_documents.extracted_formal_requirements 解析（如：正本1份、副本4份、骑缝章、逐页签字）
OCR比对项：从 ocr_extractions 对比标准库（资质有效性）
内容完整性项：检查 tech_proposal_tasks 是否所有评分项都有对应章节
规则2：风险等级定义
致命（Fatal）：导致直接废标或0分
资质有效期 < 开标日期
报价 > 预算限价（Week 4已拦截，此处二次确认）
缺少招标文件要求的强制签字页（如法定代表人签字缺失）
技术标章节缺失（评分项未响应）
警告（Warning）：可能导致扣分或质疑
资质有效期 < 合同期（覆盖开标但可能覆盖不了履约期）
签字位置不规范（如授权书日期早于营业执照）
业绩案例合同金额与文字描述不符（OCR vs 录入数据）
提示（Info）：形式合规但需注意
业绩案例即将过期（有效期临近）
使用了模板段落（建议根据实际情况微调）
规则3：人工修正的三种操作
单项确认：对系统检查项点击【确认通过】（记录 specialist_confirmed: true）
单项修正：对系统检查项点击【修正】（填写实际状况，如："系统提示缺签字，实际在第3页已签"）
全局补充：新增检查项（系统未识别，如"招标文件第8页有特殊密封要求"），填写内容+关联页码
规则4：废弃草稿库（复盘基础）
如果老板在形式审查阶段【推翻终止】（Week 2的A1硬终止模式），已生成的技术标、商务标PDF移入 abandoned_drafts 表
记录终止原因（关联到复盘库）
废弃草稿可供二次投标时参考（Week 6复盘功能）

二、数据库表设计（SQL）

    -- 形式审查检查项表（动态生成 + 人工补充）
    CREATE TABLE formal_review_items (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    
    -- 检查项来源
    source_type VARCHAR(50) CHECK (source_type IN (
        'system_parsed',      -- 系统从招标文件解析
        'ocr_comparison',     -- OCR与标准库比对发现
        'content_integrity',  -- 内容完整性检查
        'manual_added'        -- 标书专员全局补充
    )),
    parent_item_id INTEGER REFERENCES formal_review_items(id), -- 父子关系（如：资质检查→具体某证书）
    
    -- 检查内容
    check_category VARCHAR(50) CHECK (check_category IN (
        'qualification_validity',  -- 资质有效期
        'signature_seal',          -- 签字盖章
        'document_integrity',      -- 文件完整性（页码、目录）
        'price_compliance',        -- 报价合规（Week 4衔接）
        'seal_requirement',        -- 密封要求
        'format_compliance'        -- 格式合规（字体、行距等，可选）
    )),
    check_title VARCHAR(255) NOT NULL,  -- 检查标题（如："法定代表人签字检查"）
    check_description TEXT,             -- 详细描述（如："招标文件要求逐页签字，检测第5页缺少签字"）
    reference_clause TEXT,              -- 关联招标文件条款（如："第三章 3.2.1 签字要求"）
    
    -- 检查结果
    system_status VARCHAR(20) CHECK (system_status IN ('passed', 'failed', 'warning', 'uncertain')),
    system_evidence JSONB,  -- 系统判断依据（如：{"page": 5, "confidence": 0.95, "ocr_text": "..."}）
    
    -- 人工确认（三状态）
    specialist_status VARCHAR(20) CHECK (specialist_status IN ('pending', 'confirmed', 'corrected', 'deleted')),
    specialist_notes TEXT,    -- 人工备注（如："实际有签字，OCR未识别"）
    corrected_evidence TEXT,  -- 修正证据（上传图片路径或说明）
    confirmed_by INTEGER REFERENCES users(id),
    confirmed_at TIMESTAMP,
    
    -- PDF高亮坐标（用于前端渲染）
    pdf_highlight_coords JSONB,  -- {"page": 3, "x": 100, "y": 200, "width": 150, "height": 30, "color": "red"}
    
    -- 风险等级（系统初步判定，人工可修正）
    risk_level VARCHAR(20) CHECK (risk_level IN ('fatal', 'warning', 'info')),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 废弃草稿库（老板推翻终止时存档）
    CREATE TABLE abandoned_drafts (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    termination_stage VARCHAR(50),  -- 'formal_review' / 'pricing' / 'tech_generation'
    
    -- 归档内容（文件路径）
    tech_proposal_path VARCHAR(500),      -- 技术标Word/PDF
    business_proposal_path VARCHAR(500),  -- 商务标Word/PDF
    pricing_decision_id INTEGER REFERENCES pricing_decisions(id),
    
    -- 终止原因（关联复盘）
    termination_reason TEXT,
    termination_by INTEGER REFERENCES users(id),
    can_be_revived BOOLEAN DEFAULT TRUE,  -- 是否可复活（如重招项目）
    
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    revived_at TIMESTAMP,  -- 如被复活
    revived_to_project_id INTEGER REFERENCES projects(id)  -- 复活后的新项目ID
    );

    -- 最终标书生成记录
    CREATE TABLE final_bid_documents (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    
    -- 文档信息
    document_type VARCHAR(50),  -- 'complete' / 'technical_volume' / 'business_volume'
    file_path VARCHAR(500),
    file_size INTEGER,
    generated_by INTEGER REFERENCES users(id),
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 生成状态
    generation_status VARCHAR(20) CHECK (generation_status IN ('generating', 'completed', 'failed')),
    error_log TEXT,
    
    -- 封装指南（JSON存储）
    packaging_guide JSONB  -- {
                           --   "seal_bags": [{"type": "正本", "copies": 1, "label": "技术标正本"}],
                           --   "documents_checklist": ["营业执照复印件", "资质证书原件", "授权书原件"],
                           --   "special_notes": "需在密封袋封口处加盖骑缝章"
                           -- }
    );

三、核心算法逻辑（Python 伪代码）
3.1 形式审查引擎（自动检查生成器）

    class FormalReviewEngine:
    def __init__(self, project_id: int):
        self.project_id = project_id
        self.tender = db.get_tender_document(project_id)
        self.bid_docs = db.get_bid_documents(project_id)  # 技术标+商务标
        self.ocr_results = db.get_ocr_extractions(project_id)
        
    def generate_review_checklist(self) -> list:
        """
        动态生成检查清单（系统自动化部分）
        """
        checklist = []
        
        # 1. 资质有效性检查（从Week 1标准库和Week 2匹配结果）
        qual_items = db.query("""
            SELECT * FROM ocr_extractions oe
            JOIN standard_certifications sc ON oe.standard_cert_id = sc.id
            WHERE oe.image_id IN (
                SELECT id FROM document_images 
                WHERE project_id = %s AND document_type = 'bid_qualification'
            )
        """, self.project_id)
        
        for qual in qual_items:
            bid_open_date = self.tender.bid_open_date
            valid_until = qual.valid_until
            
            if valid_until < bid_open_date:
                risk = 'fatal'
                status = 'failed'
                desc = f"{qual.cert_name}有效期至{valid_until}，开标日期{bid_open_date}，**已过期**"
            elif valid_until < bid_open_date + timedelta(days=90):
                risk = 'warning'
                status = 'warning'
                desc = f"{qual.cert_name}即将过期（有效期至{valid_until}），建议在标书中承诺到期前更新"
            else:
                risk = 'info'
                status = 'passed'
                desc = f"{qual.cert_name}有效期正常（至{valid_until}）"
            
            checklist.append({
                'source_type': 'ocr_comparison',
                'check_category': 'qualification_validity',
                'check_title': f"{qual.cert_name}有效期检查",
                'check_description': desc,
                'system_status': status,
                'risk_level': risk,
                'pdf_highlight_coords': qual.bbox_coords,  # OCR时的坐标
                'reference_clause': '招标文件资质要求部分'
            })
        
        # 2. 签字盖章完整性检查（基于PDF解析和OCR）
        # 解析招标文件要求的签字位置
        required_signatures = self.parse_signature_requirements()
        # 检查投标文件实际签字（OCR识别"签字"、"签名"、"（签字）"等关键词）
        actual_signatures = self.detect_signatures_in_pdf()
        
        for req in required_signatures:
            if req['location'] not in actual_signatures:
                checklist.append({
                    'source_type': 'system_parsed',
                    'check_category': 'signature_seal',
                    'check_title': f"{req['name']}签字检查",
                    'check_description': f"招标文件要求{req['name']}在{req['page']}页签字，未检测到",
                    'system_status': 'failed',
                    'risk_level': 'fatal',
                    'pdf_highlight_coords': req['expected_coords'],  # 期望位置标红
                    'reference_clause': req['clause']
                })
        
        # 3. 技术标完整性检查（关联Week 3生成内容）
        tech_task = db.get_confirmed_tech_proposal(self.project_id)
        required_sections = json.loads(self.tender.extracted_scoring_std)
        generated_sections = json.loads(tech_task.generated_content)['sections']
        
        for req in required_sections:
            matched = any(g['section_title'] == req['name'] for g in generated_sections)
            if not matched:
                checklist.append({
                    'source_type': 'content_integrity',
                    'check_category': 'document_integrity',
                    'check_title': f"技术标章节缺失：{req['name']}",
                    'check_description': f"评分项'{req['name']}'（{req['weight']}分）在技术标中无对应章节",
                    'system_status': 'failed',
                    'risk_level': 'fatal',
                    'reference_clause': f"评分标准：{req['name']}"
                })
        
        # 4. 报价合规检查（从Week 4定价决策衔接）
        pricing = db.get_latest_pricing_decision(self.project_id)
        if pricing.boss_final_price > pricing.budget_limit:
            checklist.append({
                'source_type': 'system_parsed',
                'check_category': 'price_compliance',
                'check_title': "报价超限价检查",
                'check_description': f"定价{pricing.boss_final_price}万 > 预算限价{pricing.budget_limit}万，可能直接废标",
                'system_status': 'failed',
                'risk_level': 'fatal',
                'reference_clause': "招标文件投标须知"
            })
        
        # 批量插入数据库
        for item in checklist:
            db.insert('formal_review_items', {
                'project_id': self.project_id,
                **item,
                'specialist_status': 'pending'
            })
        
        return checklist

    def detect_signatures_in_pdf(self) -> list:
        """
        使用OCR+模板匹配检测PDF中的签字位置
        """
        # 实现：遍历PDF每一页，OCR识别"签字"、"签名"关键词位置
        # 返回检测到的签字位置列表
        pass
3.2 PDF高亮渲染引擎

    class PDFHighlighter:
    def __init__(self, input_pdf_path: str):
        self.pdf = fitz.open(input_pdf_path)
    
    def apply_highlights(self, review_items: list) -> str:
        """
        根据审查项，在PDF上添加高亮注释
        """
        for item in review_items:
            coords = item['pdf_highlight_coords']
            if not coords:
                continue
            
            page = self.pdf[coords['page'] - 1]  # PDF页码从0开始
            
            # 根据风险等级选择颜色
            color = {
                'fatal': (1, 0, 0),    # 红色
                'warning': (1, 0.8, 0), # 黄色
                'info': (0, 1, 0)       # 绿色
            }.get(item['risk_level'], (0.5, 0.5, 0.5))
            
            # 绘制高亮矩形
            rect = fitz.Rect(coords['x'], coords['y'], 
                           coords['x'] + coords['width'], 
                           coords['y'] + coords['height'])
            page.add_highlight_annot(rect)
            
            # 添加批注（显示检查项标题和状态）
            page.add_text_annot(
                (coords['x'], coords['y'] - 10),
                f"[{item['risk_level'].upper()}] {item['check_title'][:30]}...",
                icon="comment"
            )
        
        # 保存为审查版PDF
        output_path = f"/tmp/review_highlighted_{uuid4()}.pdf"
        self.pdf.save(output_path)
        return output_path

四、API 接口定义
#POST /api/projects/{project_id}/formal-review/initiate
#触发形式审查（由系统自动化生成检查项）
#Response: 生成的检查项数量 + 致命风险数量

#GET /api/projects/{project_id}/formal-review/items
#获取审查清单（支持过滤：?status=pending&risk_level=fatal）
#Response: 检查项列表，包含pdf_highlight_coords用于前端渲染

#POST /api/formal-review-items/{item_id}/confirm
#标书专员确认某项通过
class ReviewItemConfirm(BaseModel):
    notes: Optional[str]  # 可选备注

#POST /api/formal-review-items/{item_id}/correct
#标书专员修正系统判断（如：系统说缺签字，实际有）
class ReviewItemCorrect(BaseModel):
    corrected_status: str  # 'passed' or 'warning'
    corrected_evidence: str  # 说明文字或图片路径
    notes: str  # 必填：修正原因

#POST /api/formal-review-items/{item_id}/delete
#标书专员删除系统误报项（记录删除原因）

#POST /api/projects/{project_id}/formal-review/manual-add
#全局补充：新增系统未识别的检查项
class ManualReviewItem(BaseModel):
    check_category: str
    check_title: str
    check_description: str
    risk_level: str  # fatal/warning/info
    reference_clause: str  # 关联招标文件条款
    pdf_page: int  # 关联PDF页码（可选）

#GET /api/projects/{project_id}/formal-review/status
#获取整体审查状态（用于控制生成按钮）
#Response: {
#total_items: 15,
#confirmed_items: 10,
#fatal_pending: 2,  -- 致命未处理数（>0时禁止生成）
#warning_pending: 3,
#can_generate: false,  -- 是否可生成最终标书
#blocking_reason: "存在2项致命风险未处理"
#}

#POST /api/projects/{project_id}/final-documents/generate
#生成最终标书（强制前置条件：can_generate=true）
#Request: {
#include_packaging_guide: true,  -- 是否生成封装指南
#document_format: "word"  -- 目前仅支持word
#}
#Response: {
#document_id: 123,
#file_path: "/minio/final_bids/xxx.docx",
#packaging_guide: {...}  -- 封装指南JSON
#}

五、前端界面设计
5.1 形式审查工作台（双视图布局）

┌─────────────────────────────────────────────────────────────────────┐
│ 项目：XX学校食堂配送    审查状态：进行中    致命风险：2项待处理（红色）    │
├──────────────────┬──────────────────┬─────────────────────────────────┤
│   检查项列表      │   PDF预览区       │   操作面板                      │
│   （可筛选）      │   （带高亮圈注）   │                                │
├──────────────────┼──────────────────┼─────────────────────────────────┤
│ 🔴 资质过期       │                  │ 当前选中：                      │
│    ISO22000      │  [PDF页3]         │ 证书：ISO22000有效期检查        │
│    有效期检查    │                  │                                │
│    [查看] [修正]  │  ┌───────────┐   │ 系统判断：不通过（已过期）       │
│                  │  │  [证书图片]│   │ 风险等级：致命                 │
│ 🟡 签字位置      │  │  红框标注 │   │                                │
│    授权书日期    │  └───────────┘   │ [确认通过]  [修正]  [删除此项]  │
│    [查看] [确认]  │                  │                                │
│                  │  批注："有效期    │ 修正说明：                      │
│ 🟢 营业执照      │   至2025-03-01" │ ____________________________   │
│    [查看] [确认]  │                  │                                │
│                  │                  │ [全局补充新检查项]              │
├──────────────────┴──────────────────┴─────────────────────────────────┤
│ 底部操作栏                                                            │
│ 检查进度：12/15 通过 | 2 警告待确认 | 1 致命待处理                    │
│                                                                      │
│ [   🚫 生成最终标书（禁用：存在致命风险）   ]                         │
│                                                                      │
│ 提示：请处理所有致命风险（红色项）后才能生成最终标书。                  │
└─────────────────────────────────────────────────────────────────────┘

5.2 封装指南生成页（生成后展示）

最终标书已生成！文件：XX学校食堂配送_完整标书.docx (2.4MB)

封装检查清单（打印携带）：
┌────────────────────────────────────────────────────────┐
│ 密封要求（根据招标文件第三章）：                         │
│ □ 正本1份：单独密封，封口处加盖公章和法定代表人章       │
│ □ 副本4份：一起密封或分别密封（按招标文件要求）          │
│ □ 电子版U盘：装入正本袋或单独密封（注明）               │
│                                                        │
│ 文件内容检查：                                          │
│ □ 技术标：目录页、评分点索引、各章节（共45页）          │
│ □ 商务标：报价函、分项报价表、保证金凭证复印件            │
│ □ 资格标：营业执照、食品经营许可证、ISO证书（按顺序）    │
│                                                        │
│ 特殊注意事项：                                          │
│ ⚠️ 第8页授权书日期不得早于营业执照日期（已检查通过）    │
│ ⚠️ 需在密封袋封面注明"于2026-04-15 09:30前不得启封"      │
└────────────────────────────────────────────────────────┘

[下载Word标书]  [下载封装指南PDF]  [查看废弃草稿库]

六、关键业务校验规则
强制拦截逻辑：formal_review_items 表中存在 risk_level='fatal' 且 specialist_status='pending' 的记录时，POST /final-documents/generate 返回400错误，禁止生成。
误报记录：当专员点击【删除此项】时，必须填写 specialist_notes（如："系统误报，实际在第5页有签字"），用于优化OCR算法。
修正证据：点击【修正】时，如果是资质类，建议上传图片证明；如果是签字类，填写页码位置。
废弃草稿自动归档：如果老板在形式审查阶段执行 POST /projects/{id}/override (terminate)，系统自动将当前已生成的技术标、商务标文件路径写入 abandoned_drafts 表。
七、交付标准（验收 checklist）
[ ] 上传测试PDF（含过期资质扫描件），系统自动生成红色致命项，并高亮标注位置
[ ] 标书专员可在界面点击【修正】，填写说明后，该项变为绿色通过
[ ] 存在未处理致命项时，【生成最终标书】按钮禁用，点击提示具体原因
[ ] 所有致命项处理后，按钮启用，点击后生成Word（包含技术标+商务标+评分索引）
[ ] 生成Word的同时，输出封装指南（密封要求、文件清单）
[ ] 老板执行终止操作后，当前工作文件自动归档到废弃草稿库，可在复盘库查看

Week 5 核心是风险拦截的严谨性和人机协同的灵活性。PDF高亮渲染使用 PyMuPDF (fitz)，Word生成使用 python-docx（基于Week 3技术标内容+Week 4定价回填）。确保拦截逻辑100%可靠，宁可过度拦截也不要漏放风险。