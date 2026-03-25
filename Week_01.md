Week 1 开发文档：基础设施与文件解析 Pipeline（Document Intelligence & OCR Engine）
文档元信息
开发周期：Week 1（5个工作日）
前置条件：Docker 环境、PostgreSQL+pgvector、MinIO/本地存储、DeepSeek API Key
核心业务目标：实现招标文件/投标文件上传 → 扫描件 OCR → 结构化提取 → 并排确认 → 数据入库的完整 Pipeline
关键挑战：80% 投标文件内容为扫描图片（资质证书、营业执照、合同），必须实现高精度 OCR 与标准化提取
交付标准：可上传 PDF/Word → 自动提取图片 → OCR 识别 → 并排确认 → 精确匹配资质 → 保存结构化数据
一、业务逻辑架构（Week 1 核心流程）
[文件上传] ← 支持 PDF/Word，拖拽上传，保存到 MinIO/本地
    ↓
[文档解析引擎]
    ├─ 文本提取：pdfplumber / python-docx（可搜索文本层）
    ├─ 图片提取：PyMuPDF (fitz) 提取所有内嵌图片（扫描件）
    └─ 图片预处理：去重(MD5)、分类（营业执照/证书/合同/身份证）
    ↓
[OCR 识别引擎] ← PaddleOCR（本地部署，中文优化）
    ├─ 营业执照：提取统一社会信用代码、经营范围、有效期
    ├─ 资质证书：提取证书名称、编号、颁发机构、有效期、等级（一级/二级）
    ├─ 合同页：提取金额、甲方、签订日期
    └─ 身份证/人员证：提取姓名、证号、有效期
    ↓
[标准化清洗] ← 正则提取 + LLM 后处理（DeepSeek）
    ├─ 证书名称标准化（"建筑工程施工总承包一级" ≠ "二级"）
    ├─ 日期标准化（2025年3月 → 2025-03-01）
    └─ 等级关键词提取（特级/一级/二级/甲级/乙级）
    ↓
[并排确认界面] ← 三角色可见（专员为主）
    ├─ 左侧：PDF 原图渲染（滚动定位）
    ├─ 中间：OCR 提取图片缩略图（点击放大）
    └─ 右侧：结构化表单（可编辑，低置信度标红）
    ↓
[精确匹配校验] ← 对比 standard_certifications 库
    ├─ 必须包含关键词检查
    ├─ 必须排除关键词检查（防止经营证误判为生产证）
    ├─ 等级精确匹配（一级 ≠ 二级）
    └─ 有效期覆盖检查（资质有效期 ≥ 开标日期？）
    ↓
[数据入库] ← 保存到 Week 1 数据库表，供 Week 2-8 使用

二、数据库表设计（Week 1 基础表）
    -- 项目主表（贯穿 Week 1-8）
    CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    project_name VARCHAR(255) NOT NULL,        -- 项目名称（从招标文件解析）
    project_type VARCHAR(50),                  -- 学校食堂/政府物业/医院
    owner_unit VARCHAR(255),                   -- 业主单位（招标方）
    owner_type VARCHAR(50) CHECK (owner_type IN ('school', 'government', 'hospital', 'enterprise')),
    region VARCHAR(100),                       -- 地区（用于地域匹配）
    
    budget_amount DECIMAL(15,2),               -- 预算金额（从招标文件解析）
    bid_open_date TIMESTAMP,                   -- 开标日期（关键！用于有效期检查）
    
    status VARCHAR(50) DEFAULT 'uploaded' 
        CHECK (status IN ('uploaded', 'parsing', 'parsed', 'evaluating', 'evaluation_ready', 
                         'approved_by_specialist', 'rejected_by_specialist', 'terminated_by_boss',
                         'generating_documents', 'awaiting_pricing', 'awaiting_review', 'completed')),
    
    relationship_flag BOOLEAN DEFAULT FALSE,   -- 是否有内幕关系（Week 2 标记）
    
    created_by INTEGER REFERENCES users(id),   -- 标书专员/老板
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 招标文件解析表（Week 1 核心产出）
    CREATE TABLE tender_documents (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    
    file_path VARCHAR(500),                    -- MinIO/本地存储路径
    file_type VARCHAR(10) CHECK (file_type IN ('pdf', 'word')),
    
    -- 解析状态
    parsing_status VARCHAR(20) DEFAULT 'pending' 
        CHECK (parsing_status IN ('pending', 'extracting', 'ocr_processing', 'structuring', 'completed', 'failed')),
    
    -- 结构化提取结果（JSON）
     extracted_data JSONB,                      
     {
     -- "project_name": "...",
     -- "budget": 1500000,
     -- "bid_open_date": "2026-04-15T09:00:00",
     --   "scoring_standard": {
     --     "technical": 40, "business": 30, "price": 30,
     --     "items": [{"name": "配送方案", "weight": 20, "criteria": "..."}]
     --   },
     --   "qualification_requirements": [
     --     {"cert_code": "FOOD-BUSINESS", "is_mandatory": true}
      ],
     --   "formal_requirements": {
     --     "original_copies": 1, "duplicate_copies": 4,
     --     "seal_requirements": ["骑缝章", "逐页签字"]
     --   }
     -- }
    
    parsed_by_ai BOOLEAN DEFAULT FALSE,        -- 是否经 LLM 解析
    confirmed_by_human BOOLEAN DEFAULT FALSE,  -- 专员是否确认（并排确认界面）
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id)                         -- 一个项目对应一份招标文件
    );

    -- 投标文件文档表（资质文件存储）
    CREATE TABLE bid_documents (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    doc_type VARCHAR(50) CHECK (doc_type IN ('qualification', 'technical', 'business', 'pricing')),
    file_path VARCHAR(500),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 文档图片表（从 PDF 提取的扫描件原图）
    CREATE TABLE document_images (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES bid_documents(id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(id),  -- 冗余字段，方便查询
    
    image_path VARCHAR(500),                   -- 图片存储路径（PNG/JPG）
    page_number INTEGER,                       -- 在 PDF 中的页码
    image_hash VARCHAR(64),                    -- MD5 去重
    image_type VARCHAR(50),                    -- business_license / certification / contract / id_card / other
    
    ocr_status VARCHAR(20) DEFAULT 'pending' CHECK (ocr_status IN ('pending', 'processing', 'success', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- OCR 提取结果表（结构化数据）
    CREATE TABLE ocr_extractions (
    id SERIAL PRIMARY KEY,
    image_id INTEGER REFERENCES document_images(id),
    project_id INTEGER REFERENCES projects(id),
    
    -- OCR 识别字段
    field_name VARCHAR(50) CHECK (field_name IN (
        'cert_name', 'cert_number', 'issuing_authority', 
        'valid_from', 'valid_until', 'business_scope',
        'company_name', 'credit_code', 'legal_representative',
        'person_name', 'person_id', 'contract_amount', 'contract_date'
    )),
    field_value TEXT,                          -- 提取的文本值
    confidence_score DECIMAL(4,3),             -- OCR 置信度 0-1
    
    -- 标准化后数据（清洗后的）
    normalized_value TEXT,                     -- 标准化值（如日期统一为 YYYY-MM-DD）
    standard_cert_id INTEGER REFERENCES standard_certifications(id), -- 关联到标准库（如识别出是 ISO22000）
    
    -- 人工校验（Week 1 并排确认时修正）
    is_validated BOOLEAN DEFAULT FALSE,
    validated_by INTEGER REFERENCES users(id),
    validation_notes TEXT,
    
    raw_text TEXT,                             -- OCR 原始完整文本（上下文）
    bbox_coords JSONB,                         -- 图片中的坐标 {x, y, width, height}，用于 Week 5 PDF 高亮
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    标准资质库（Week 1 预初始化，基于用户业务预生成）
    CREATE TABLE standard_certifications (
    id SERIAL PRIMARY KEY,
    cert_code VARCHAR(50) UNIQUE NOT NULL,     -- 标准编码如 FOOD-BUSINESS-LICENSE
    cert_full_name VARCHAR(255) NOT NULL,      -- 全称：食品经营许可证
    cert_short_name VARCHAR(100),              -- 简称：食品经营许可
    aliases JSONB,                             -- 别名：["食品流通许可证"]
    
    -- 匹配规则（精确匹配核心）
    required_keywords JSONB NOT NULL,          -- 必须包含：["食品经营", "许可证"]
    exclude_keywords JSONB NOT NULL,           -- 必须排除：["生产", "小作坊"]（防止误判）
    
    -- 识别特征
    cert_number_pattern VARCHAR(100),          -- 正则：^([0-9A-Z]{14})$
    issuing_authority_keywords JSONB,          -- 颁发机构关键词：["市场监督管理局"]
    
    -- 业务属性
    category VARCHAR(50),                      -- food / construction / iso / personnel
    validity_years INTEGER,                      -- 默认有效期（年）
    is_mandatory_for_food_delivery BOOLEAN DEFAULT FALSE,
    is_mandatory_for_property BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 初始化数据（食材配送 + 物业业务，用户预生成 SQL 见下方）
    INSERT INTO standard_certifications VALUES
    ('BUSINESS-LICENSE', '营业执照', '营业执照', 
    '["营业执照"]', '["副本", "吊销"]', '^([0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10})$',
    '["市场监督管理局"]', 'enterprise', 0, true, true, true),

    ('FOOD-BUSINESS-LICENSE', '食品经营许可证', '食品经营许可证', 
    '["食品经营", "许可证"]', '["生产", "小作坊"]', '^([0-9A-Z]{14})$',
    '["市场监督管理局"]', 'food', 5, true, false, true),

    ('FOOD-PRODUCTION-LICENSE', '食品生产许可证', '食品生产许可证',
    '["食品生产", "许可证"]', '["经营", "流通"]', '^(SC\d{14})$',
    '["市场监督管理局"]', 'food', 5, false, false, true),

    ('ISO-22000-2018', 'ISO 22000:2018 食品安全管理体系认证', 'ISO 22000',
    '["ISO", "22000", "食品安全"]', '["ISO 9001", "质量管理体系"]', null,
    '["SGS", "中国质量认证中心"]', 'iso', 3, false, false, true),

    ('PROP-SVC-LVL1', '物业服务企业一级资质', '物业一级资质',
    '["物业", "服务", "一级"]', '["二级", "三级"]', null,
    '["住房和城乡建设部"]', 'property', 0, false, true, true);

 三、核心算法逻辑（Python 伪代码）

3.1 OCR Pipeline（扫描件处理）

    class DocumentOCRPipeline:
    """
    Week 1 核心：处理扫描件 PDF，提取结构化资质信息
    """
    
    def __init__(self):
        self.paddleocr = PaddleOCR(
            use_angle_cls=True,           # 方向分类（处理颠倒图片）
            lang='ch',                    # 中文模型
            gpu=False,                    # CPU 运行（Docker 适配）
            show_log=False
        )
        self.llm = DeepSeekClient(api_key=os.getenv("DEEPSEEK_API_KEY"))
    
    def process_pdf(self, pdf_path: str, project_id: int) -> dict:
        """
        完整 Pipeline：PDF → 图片 → OCR → 结构化 → 入库
        """
        # 1. 提取图片（PyMuPDF）
        doc = fitz.open(pdf_path)
        images = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            img_list = page.get_images(full=True)
            
            for img_idx, img in enumerate(img_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]  # png/jpeg
                
                # MD5 去重
                img_hash = hashlib.md5(image_bytes).hexdigest()
                if db.exists_image_hash(img_hash):
                    continue
                
                # 保存图片
                img_filename = f"{project_id}_p{page_num}_{img_idx}.{image_ext}"
                img_path = f"/minio/images/{img_filename}"
                with open(img_path, "wb") as f:
                    f.write(image_bytes)
                
                # 图片分类（LLM 或规则初分）
                img_type = self.classify_image_type(image_bytes)
                
                img_record = {
                    'project_id': project_id,
                    'image_path': img_path,
                    'page_number': page_num + 1,
                    'image_hash': img_hash,
                    'image_type': img_type,  # business_license/certification/contract/other
                    'ocr_status': 'pending'
                }
                img_id = db.insert('document_images', img_record)
                images.append({'id': img_id, 'path': img_path, 'type': img_type})
        
        # 2. 对每张图片 OCR 识别
        for img in images:
            self.ocr_image(img['id'], img['path'], img['type'])
        
        return {'processed_images': len(images), 'status': 'success'}
    
    def ocr_image(self, image_id: int, image_path: str, image_type: str):
        """
        单张图片 OCR 与结构化
        """
        # PaddleOCR 识别
        result = self.paddleocr.ocr(image_path, cls=True)
        
        # 合并文本
        raw_text = "\n".join([line[1][0] for line in result[0]])
        
        # 根据图片类型，LLM 提取结构化字段
        if image_type == 'business_license':
            structured = self.extract_business_license(raw_text)
        elif image_type == 'certification':
            structured = self.extract_certification(raw_text)
        elif image_type == 'contract':
            structured = self.extract_contract(raw_text)
        else:
            structured = {'general_text': raw_text}
        
        # 标准化清洗
        normalized = self.normalize_extraction(structured)
        
        # 精确匹配标准库（尝试识别是什么证书）
        standard_match = self.match_to_standard(normalized)
        
        # 入库
        for field, value in normalized.items():
            confidence = 0.85  # PaddleOCR 平均置信度，可细化
            
            db.insert('ocr_extractions', {
                'image_id': image_id,
                'field_name': field,
                'field_value': value['original'],
                'normalized_value': value['normalized'],
                'confidence_score': confidence,
                'standard_cert_id': standard_match.get('cert_id') if field == 'cert_name' else None,
                'raw_text': raw_text[:1000],  # 存储上下文
                'bbox_coords': value.get('bbox')  # 坐标用于 Week 5 高亮
            })
        
        # 更新图片状态
        db.update('document_images', {'id': image_id, 'ocr_status': 'success'})
    
    def normalize_extraction(self, structured: dict) -> dict:
        """
        标准化清洗（关键！Week 1 必须做好，Week 2 才能精确匹配）
        """
        normalized = {}
        
        for field, value in structured.items():
            clean_value = value.strip()
            
            # 中文数字转阿拉伯数字
            clean_value = clean_value.replace('壹', '一').replace('贰', '二').replace('叁', '三')
            
            # 日期标准化
            if '日期' in field or 'valid' in field:
                # 正则提取日期，统一为 YYYY-MM-DD
                date_match = re.search(r'(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})', clean_value)
                if date_match:
                    normalized[field] = {
                        'original': value,
                        'normalized': f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
                    }
            
            # 统一社会信用代码格式化（18位）
            elif field == 'credit_code':
                clean_value = re.sub(r'[^0-9A-Z]', '', clean_value).upper()
                if len(clean_value) == 18:
                    normalized[field] = {'original': value, 'normalized': clean_value}
            
            # 证书名称标准化（用于 Week 2 精确匹配）
            elif field == 'cert_name':
                # 去除空格、统一括号
                clean_value = clean_value.replace(' ', '').replace('（', '(').replace('）', ')')
                normalized[field] = {'original': value, 'normalized': clean_value}
        
        return normalized
    
    def match_to_standard(self, normalized: dict) -> dict:
        """
        尝试匹配标准资质库（Week 2 的预演，Week 1 先记录匹配建议）
        """
        if 'cert_name' not in normalized:
            return {}
        
        cert_name = normalized['cert_name']['normalized']
        
        # 查询所有标准证书，尝试精确匹配
        standards = db.query("SELECT * FROM standard_certifications WHERE is_active = true")
        
        for std in standards:
            required = json.loads(std['required_keywords'])
            excluded = json.loads(std['exclude_keywords'])
            
            # 检查必须包含
            if all(kw in cert_name for kw in required):
                # 检查必须排除
                if not any(kw in cert_name for kw in excluded):
                    # 等级检查（如一级/二级）
                    if '一级' in std['cert_full_name'] and '一级' not in cert_name:
                        continue
                    
                    return {'cert_id': std['id'], 'cert_code': std['cert_code']}
        
        return {}

3.2 并排确认界面后端 API

    class SideBySideConfirmationAPI:
    """
    Week 1 前端需要的 API：并排展示 PDF 原图 + OCR 结果 + 可编辑表单
    """
    
    def get_confirmation_data(self, project_id: int) -> dict:
        """
        获取并排确认界面所需全部数据
        """
        project = db.get_project(project_id)
        tender = db.get_tender_document(project_id)
        
        # 获取所有图片及 OCR 结果
        images = db.query("""
            SELECT di.*, 
                   json_agg(json_build_object(
                       'field_name', oe.field_name,
                       'field_value', oe.field_value,
                       'normalized_value', oe.normalized_value,
                       'confidence', oe.confidence_score,
                       'is_validated', oe.is_validated
                   )) as ocr_fields
            FROM document_images di
            LEFT JOIN ocr_extractions oe ON oe.image_id = di.id
            WHERE di.project_id = %s
            GROUP BY di.id
        """, project_id)
        
        # 按页码排序
        images.sort(key=lambda x: x['page_number'])
        
        # 标记低置信度（需人工确认）
        for img in images:
            img['needs_review'] = any(
                f['confidence'] < 0.8 and not f['is_validated'] 
                for f in img['ocr_fields']
            )
        
        return {
            'project': project,
            'tender': tender,
            'images': images,
            'total_images': len(images),
            'pending_review': sum(1 for img in images if img['needs_review'])
        }
    
    def confirm_parsing_result(self, project_id: int, confirmations: list, user_id: int) -> dict:
        """
        专员确认解析结果（提交并排确认界面编辑后的数据）
        """
        for conf in confirmations:
            # 更新 OCR 提取结果（人工修正）
            if conf['action'] == 'correct':
                db.update('ocr_extractions', {
                    'id': conf['extraction_id'],
                    'normalized_value': conf['corrected_value'],
                    'is_validated': True,
                    'validated_by': user_id,
                    'validation_notes': conf.get('notes', '人工修正')
                })
            elif conf['action'] == 'confirm':
                db.update('ocr_extractions', {
                    'id': conf['extraction_id'],
                    'is_validated': True,
                    'validated_by': user_id
                })
        
        # 标记招标文件已确认
        db.update('tender_documents', {
            'project_id': project_id,
            'confirmed_by_human': True,
            'parsing_status': 'completed'
        })
        
        # 触发 Week 2 初筛报告生成（可选，或手动触发）
        # trigger_week2_evaluation(project_id)
        
        return {'status': 'confirmed', 'next_step': 'evaluation'}
四、API 接口定义
#POST /api/projects
#创建新项目（空的，准备上传文件）
class ProjectCreate(BaseModel):
    project_name: Optional[str] = None  # 可空，解析后回填
    owner_unit: Optional[str] = None
    created_by: int

#POST /api/projects/{project_id}/upload
#上传招标文件（PDF/Word）
#Content-Type: multipart/form-data
#Response: {file_id, upload_status, extracted_preview: {...}}

#GET /api/projects/{project_id}/confirmation-data
#获取并排确认界面数据
#Response: {project, images: [{page_number, image_url, ocr_fields, needs_review}], total_pages}

#POST /api/projects/{project_id}/confirm-parsing
#提交确认结果（人工修正后的数据）
class ParsingConfirm(BaseModel):
    confirmations: List[dict]  # [{extraction_id, action: 'confirm'|'correct', corrected_value, notes}]

#GET /api/ocr-extractions/{extraction_id}
#获取单条 OCR 详情（用于编辑时加载）

#POST /api/standard-certifications/match-preview
#预览：某文本匹配到哪个标准证书（测试用）
class MatchPreview(BaseModel):
    cert_name_text: str
#Response: {matched_cert: {cert_code, cert_full_name, confidence}, match_details}

#GET /api/document-images/{image_id}/view
#查看原图（用于并排界面左侧）

五、前端界面设计（并排确认界面）
┌─────────────────────────────────────────────────────────────────────┐
│ 招标文件解析确认（项目名称提取：XX学校食堂配送）                      │
├─────────────────────────────────────────────────────────────────────┤
│ 左侧：PDF 原图渲染          │  中间：缩略图导航    │ 右侧：结构化表单    │
├───────────────────────────┼──────────────────────┼──────────────────┤
│                           │                      │                   │
│  [PDF 渲染区域]             │  P1 [缩略图]         │  【当前选中图片】   │
│  支持滚动、缩放             │  P2 [缩略图]       │  页码：第 3 页      │
│  点击坐标跳转               │  P3 [缩略图]       │  类型：营业执照     │
│                           │  P4 [缩略图]         │                   │
│  [放大] [缩小] [旋转]      │                      │  OCR 识别结果：     │
│                           │  图例： 致命错误    │  • 统一社会信用代码 │
│                           │        需确认      │    [91110108...]  │
│                           │                      │    置信度：0.92   │
│                           │                      │                   │
│                           │                      │  • 经营范围       │
│                           │                      │    [餐饮服务...]  │
│                           │                      │    置信度：0.65  │
│                           │                      │    [修正]         │
│                           │                      │                   │
│                           │                      │  • 有效期至       │
│                           │                      │    [2025-12-31]   │
│                           │                      │     已过期！     │
│                           │                      │                   │
│                           │                      │  [确认无误] [保存修正] │
│                           │                      │                   │
├───────────────────────────┴──────────────────────┴──────────────────┤
│ 解析进度：12/15 页完成 | 3 项需人工确认 | 1 项致命错误（资质过期）   │
│                                                                      │
│ [暂存草稿]    [确认解析结果并生成初筛报告 →]                        │
└─────────────────────────────────────────────────────────────────────┘
六、关键业务校验规则
OCR 置信度标记：confidence_score < 0.8 自动标记黄色警告，必须人工确认或修正后才能提交。
致命错误拦截：检测到资质有效期 < 开标日期时，标记红色致命错误，需在右侧明显提示。
图片去重：MD5 哈希相同图片只处理一次，防止重复 OCR 浪费资源。
标准库匹配预览：即使 Week 2 才正式匹配，Week 1 也要在确认界面显示"疑似证书类型：食品经营许可证（建议）"。
数据完整性：确认提交时，所有 ocr_extractions 记录必须有 is_validated=true，否则提示"还有未确认项"。
七、交付标准（Week 1 验收 checklist）
[ ] 上传含扫描营业执照的 PDF，系统自动提取图片，PaddleOCR 识别出统一社会信用代码和经营范围
[ ] 并排确认界面显示：左侧 PDF 第 3 页，右侧自动识别出"营业执照"类型及字段
[ ] 低置信度字段（<0.8）自动标黄，人工修正后保存，数据库记录 is_validated=true
[ ] 资质有效期 2025-12-31，开标日期 2026-04-15，系统自动提示红色"已过期"警告
[ ] 点击"确认解析结果"，项目状态变为 parsed，可进入 Week 2 初筛报告生成
[ ] Docker Compose 一键启动（PostgreSQL+pgvector+PaddleOCR+FastAPI+MinIO）

Week 1 是整个系统的数据基石，必须确保：
PaddleOCR 正确部署（中文模型，支持方向分类）
图片提取逻辑健壮（处理多层嵌套 PDF、超大文件）
标准化清洗严格（日期格式、证书名称、等级关键词）
并排确认界面可用（即使简陋，但必须能展示 PDF+OCR 结果+编辑保存）
Week 1 完成后，系统应具备"看懂"扫描件资质的能力，为 Week 2 的精确匹配和致命拦截提供数据基础。