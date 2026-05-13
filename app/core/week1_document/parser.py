"""Document OCR Pipeline - Main Orchestrator."""
from pathlib import Path
from typing import Optional
import logging
import re
import fitz  # PyMuPDF
from sqlalchemy.orm import Session

from app.core.week1_document.image_extractor import ImageExtractor
from app.core.week1_document.ocr_engine import OCREngine, FieldConfidence
from app.utils.datetime_utils import parse_ocr_date
from app.utils.text_utils import normalize_ocr_text
from app.core.week1_document.cert_matcher import StandardCertMatcher
from app.models.document import DocumentImage, OcrExtraction, BidDocument, TenderDocument
from app.core.week1_document.qualification_extractor import extract_qualifications_with_llm
from app.models.project import Project

logger = logging.getLogger(__name__)


class DocumentOCRPipeline:
    """Document OCR Pipeline orchestrating image extraction, OCR, and storage.

    This pipeline:
    1. Extracts images from PDF using ImageExtractor (MD5 deduplication)
    2. Recognizes text using OCREngine
    3. Normalizes OCR text and dates using Task 4 utils
    4. Suggests standard cert matches using StandardCertMatcher
    5. Stores results to ocr_extractions table with is_validated=False
    """

    def __init__(self, db: Session):
        """Initialize pipeline with database session.

        Args:
            db: SQLAlchemy database session.
        """
        self.db = db
        self.image_extractor = ImageExtractor()
        self.ocr_engine = OCREngine()
        self.cert_matcher = StandardCertMatcher(db)

    def process_pdf(self, pdf_path: str, project_id: int) -> dict:
        """Process a PDF document through the OCR pipeline.

        Args:
            pdf_path: Path to the PDF file.
            project_id: ID of the project this document belongs to.

        Returns:
            Dict with processing results {'processed_images': int, 'status': str}
        """
        project = self.db.query(Project).get(project_id)
        if project:
            project.status = 'parsing'
            self.db.commit()

        try:
            # Get or create a BidDocument for this project
            bid_doc = self.db.query(BidDocument).filter_by(project_id=project_id).first()
            if not bid_doc:
                bid_doc = BidDocument(project_id=project_id, doc_type='business')
                self.db.add(bid_doc)
                self.db.flush()

            images = self.image_extractor.extract_images(pdf_path)
            processed_count = 0

            for img_data in images:
                try:
                    self._process_single_image(
                        image_bytes=img_data.image_bytes,
                        page_number=img_data.page_number,
                        md5_hash=img_data.md5_hash,
                        project_id=project_id,
                        image_ext=img_data.image_ext,
                        document_id=bid_doc.id,
                    )
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Failed to process image: {e}")

            # Fallback: if no images extracted (text-based PDF), extract text directly
            qualification_requirements = []
            plan_code = None
            agency_project_code = None
            if processed_count == 0:
                # Text-based PDF: extract text and qualifications together
                processed_count, qualification_requirements, plan_code, agency_project_code = self._process_text_pdf(
                    pdf_path, project_id, bid_doc.id
                )
            else:
                # Image-based PDF: still extract text for qualification requirements
                # (qualifications come from the tender document text, not the OCR images)
                try:
                    qualification_requirements = self._extract_qualifications_from_pdf(pdf_path)
                    # Also extract plan codes from full PDF text for image-based PDFs
                    plan_code, agency_project_code = self._extract_plan_codes_from_pdf(pdf_path)
                except Exception as e:
                    logger.warning(f"Failed to extract qualifications from image PDF: {e}")

            # Write plan codes directly to TenderDocument and Project
            tender_doc = self.db.query(TenderDocument).filter_by(project_id=project_id).first()
            if tender_doc:
                if plan_code:
                    tender_doc.plan_code = plan_code
                if agency_project_code:
                    tender_doc.agency_project_code = agency_project_code
            if project:
                if plan_code:
                    project.plan_code = plan_code
                if agency_project_code:
                    project.agency_project_code = agency_project_code
            self.db.commit()

            # Create TenderDocument with extracted qualification requirements
            if qualification_requirements:
                tender_doc = self.db.query(TenderDocument).filter_by(project_id=project_id).first()
                if not tender_doc:
                    tender_doc = TenderDocument(
                        project_id=project_id,
                        file_path=pdf_path,
                        file_type='pdf',
                        parsing_status='parsed',
                        extracted_data={'qualification_requirements': qualification_requirements},
                        confirmed_by_human=False,
                        plan_code=plan_code,
                        agency_project_code=agency_project_code,
                    )
                    self.db.add(tender_doc)
                else:
                    # Update existing tender doc with new requirements
                    existing = tender_doc.extracted_data or {}
                    existing['qualification_requirements'] = qualification_requirements
                    tender_doc.extracted_data = existing
                    tender_doc.parsing_status = 'parsed'
                self.db.commit()
                logger.info(f"Created TenderDocument for project {project_id} with {len(qualification_requirements)} qualification requirements")

            if project:
                project.status = 'parsed'
                self.db.commit()

            return {'processed_images': processed_count, 'status': 'success'}
        except Exception as e:
            if project:
                project.status = 'parse_failed'
                self.db.commit()
            raise

    def _process_single_image(
        self,
        image_bytes: bytes,
        page_number: int,
        md5_hash: str,
        project_id: int,
        image_ext: str,
        document_id: int,
    ) -> None:
        """Process a single image through OCR and store results.

        Args:
            image_bytes: Raw image bytes.
            page_number: Page number in the original PDF.
            md5_hash: MD5 hash of the image for deduplication.
            project_id: ID of the project.
            image_ext: Image file extension.
            document_id: ID of the parent BidDocument.
        """
        image_path = self._save_image(image_bytes, project_id, page_number, image_ext)
        image_type = self.image_extractor.classify_image_type(image_bytes)

        doc_image = DocumentImage(
            document_id=document_id,
            project_id=project_id,
            image_path=image_path,
            page_number=page_number,
            image_hash=md5_hash,
            image_type=image_type,
            ocr_status='processing',
        )
        self.db.add(doc_image)
        self.db.flush()

        ocr_result = self.ocr_engine.recognize(image_path, image_type)

        for field_conf in ocr_result.fields:
            self._store_extraction(
                image_id=doc_image.id,
                project_id=project_id,
                field=field_conf,
                raw_text=ocr_result.raw_text,
            )

        doc_image.ocr_status = 'success'
        self.db.commit()

    def _store_extraction(
        self,
        image_id: int,
        project_id: int,
        field: FieldConfidence,
        raw_text: str,
    ) -> None:
        """Store an OCR extraction result to the database.

        Args:
            image_id: ID of the DocumentImage.
            project_id: ID of the project.
            field: FieldConfidence object with field details.
            raw_text: Raw OCR text from the image.
        """
        normalized = self._normalize_field(field)
        cert_suggestion = None
        if field.field == 'cert_name':
            cert_suggestion = self.cert_matcher.suggest_match(field.value)

        extraction = OcrExtraction(
            image_id=image_id,
            project_id=project_id,
            field_name=field.field,
            field_value=field.value,
            confidence_score=field.confidence,
            normalized_value=normalized,
            standard_cert_id=cert_suggestion['cert_id'] if cert_suggestion else None,
            raw_text=raw_text[:2000] if raw_text else None,
            bbox_coords=field.bbox,
            is_validated=True,  # Text-based PDF extraction is auto-confirmed
        )
        self.db.add(extraction)

    def _normalize_field(self, field: FieldConfidence) -> str:
        """Normalize field value using text utils and date parser.

        Args:
            field: FieldConfidence object with field details.

        Returns:
            Normalized field value string.
        """
        val = normalize_ocr_text(field.value)
        if 'date' in field.field.lower() or 'valid' in field.field.lower():
            parsed = parse_ocr_date(field.value)
            if parsed:
                val = str(parsed)
        return val

    def _save_image(
        self,
        image_bytes: bytes,
        project_id: int,
        page_number: int,
        image_ext: str,
    ) -> str:
        """Save image bytes to a temporary file.

        Args:
            image_bytes: Raw image bytes.
            project_id: ID of the project.
            page_number: Page number in the original PDF.
            image_ext: Image file extension.

        Returns:
            Path to the saved image file.
        """
        import tempfile
        filename = f"{project_id}_p{page_number}.{image_ext}"
        tmp_dir = Path(tempfile.gettempdir()) / "tis_images"
        tmp_dir.mkdir(exist_ok=True)
        filepath = tmp_dir / filename
        filepath.write_bytes(image_bytes)
        return str(filepath)

    def _process_text_pdf(self, pdf_path: str, project_id: int, document_id: int) -> tuple[int, list[dict], Optional[str], Optional[str]]:
        """Extract structured fields from a text-based (non-scanned) PDF.

        Uses PyMuPDF to read plain text from each page, then applies regex
        patterns to extract key tender document fields.

        Args:
            pdf_path: Path to the PDF file.
            project_id: ID of the project.
            document_id: ID of the parent BidDocument.

        Returns:
            Tuple of (processed_page_count, qualification_requirements, plan_code, agency_project_code).
        """
        doc = fitz.open(str(pdf_path))
        processed = 0

        try:
            # Collect all text from first 10 pages (covers most tender docs)
            all_pages_text = []
            for page_num in range(min(10, len(doc))):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    all_pages_text.append((page_num + 1, text))

            if not all_pages_text:
                raise ValueError("PDF has no extractable text (possibly scanned-only or password-protected)")

            # Merge all text for field extraction
            full_text = "\n".join(text for _, text in all_pages_text)
            # Collapse spaced characters (e.g. "惠 州 市" -> "惠州市")
            full_text = re.sub(r' (?=[\\u4e00-\\u9fff])', '', full_text)

            # Create one DocumentImage "page" entry per extracted page for UI reference
            for page_num, text in all_pages_text:
                collapsed = re.sub(r' (?=[\\u4e00-\\u9fff])', '', text)
                doc_image = DocumentImage(
                    document_id=document_id,
                    project_id=project_id,
                    image_path=pdf_path,  # Store PDF path as reference
                    page_number=page_num,
                    image_hash="",
                    image_type="text_page",
                    ocr_status="success",
                )
                self.db.add(doc_image)
                self.db.flush()

                # Extract fields from this page's text (pass raw text, extraction handles spaces)
                fields = self._extract_fields_from_text(text, page_num)
                for field_conf in fields:
                    self._store_extraction(
                        image_id=doc_image.id,
                        project_id=project_id,
                        field=field_conf,
                        raw_text=collapsed[:2000],
                    )
                processed += 1

            self.db.commit()
        finally:
            doc.close()

        # Extract qualification requirements from the full merged text
        requirements = self.extract_qualification_requirements(full_text)

        # Extract plan codes from the full merged text (not per-page)
        plan_code, agency_project_code = self._extract_plan_codes_from_text(full_text)

        return processed, requirements, plan_code, agency_project_code

    def _extract_fields_from_text(self, text: str, page_num: int) -> list[FieldConfidence]:
        """Extract structured tender document fields from plain text.

        Args:
            text: Raw (not collapsed) PDF page text.
            page_num: Page number for field attribution.

        Returns:
            List of FieldConfidence objects for each extracted field.
        """
        fields = []

        # Known label prefixes to strip from OCR extraction values
        LABEL_PREFIXES = (
            '项目名称：', '采购人：', '招标人：', '业主单位：',
            '采购计划编号：', '采购项目编号：', '采购代理机构：',
            '预算金额：', '采购预算：', '地址：', '联系方式：',
        )

        def de_space(s: str) -> str:
            """Remove all ASCII spaces from string (OCR spaces between Chinese chars)."""
            return re.sub(r' +', '', s)

        def clean_value(val: str) -> str:
            """Remove label prefixes that OCR may have included in the value."""
            val = de_space(val)
            for prefix in LABEL_PREFIXES:
                if val.startswith(prefix):
                    val = val[len(prefix):]
                    break
            return val.strip()

        def get_field_value(label: str) -> str:
            """Extract clean field value from text-based tender PDFs."""
            idx = text.find(label)
            if idx < 0:
                return ''

            val_end = text.find('\n', idx)
            if val_end < 0:
                val_end = len(text)

            # Skip ASCII space between label and value (OCR artifact)
            val_start = idx + len(label)
            if val_start < len(text) and text[val_start] == ' ':
                val_start += 1

            # Get content immediately after label on the same line
            same_line = text[val_start:val_end].strip()

            if same_line:
                # Value is right after label on same line
                val = de_space(same_line)
                val = clean_value(val)
                return val

            # Value is on the NEXT line
            next_start = val_end + 1
            next_end = text.find('\n', next_start)
            if next_end < 0:
                next_end = len(text)
            next_line = text[next_start:next_end].strip()

            if next_line:
                val = de_space(next_line)
                # Skip if next line starts with a section header (different label)
                # e.g. "采购人信息" starts with "采购" but is NOT "采购人："
                # Only skip if the first 4 chars of next_line differ from first 4 of label
                label_4 = label[:4] if len(label) >= 4 else label
                next_4 = next_line[:4] if len(next_line) >= 4 else next_line
                if next_4 != label_4:
                    # Different first chars — might be a section header artifact
                    skip_markers = ('信息', '名称', '编号', '方式', '金额', '地址', '电话', '联系人')
                    if any(marker in next_4 for marker in skip_markers):
                        return ''
                val = clean_value(val)
                return val

            return ''

        # 1. Project name — "项目名称：" on page 1
        if page_num == 1:
            name = get_field_value('项目名称：')
            if name and len(name) >= 5:
                fields.append(FieldConfidence(
                    field='project_name',
                    value=name,
                    confidence=0.95,
                ))

        # 2. Owner/procuring entity — "采购人：" or "招标人："
        owner = get_field_value('采购人：')
        if not owner or len(owner) < 2:
            owner = get_field_value('招标人：')
        if not owner or len(owner) < 2:
            owner = get_field_value('业主单位：')
        if owner and len(owner) >= 2:
            fields.append(FieldConfidence(
                field='owner_unit',
                value=owner,
                confidence=0.95,
            ))

        # 3. Budget amount — "预算金额：9,000,000.00元"
        budget_val = get_field_value('预算金额：')
        if not budget_val:
            budget_val = get_field_value('采购预算：')
        m = re.search(r'([0-9][0-9,.]{2,20})', budget_val)
        if m:
            amount_str = m.group(1).replace(',', '').strip()
            try:
                amount = float(amount_str)
                if amount > 0:
                    fields.append(FieldConfidence(
                        field='budget_amount',
                        value=str(int(amount)),
                        confidence=0.90,
                    ))
            except ValueError:
                pass

        # 4. Region — from address field
        region = get_field_value('地址：')
        if region and len(region) >= 4:
            # Extract just province+city: "广东省惠州市" from full address
            m = re.search(r'(广东省[^\s\d\-A-Za-z]{0,15}市)', region)
            if m:
                region = m.group(1).strip()
            else:
                # Trim trailing phone numbers, coordinates
                region = re.sub(r'[\d\-\sA-Za-z]{4,}$', '', region).strip()
            if region and len(region) >= 4 and not region.startswith('采购'):
                fields.append(FieldConfidence(
                    field='region',
                    value=region,
                    confidence=0.80,
                ))

        # 5a. 采购计划编号 — regex: 441301-2025-03605
        plan_code_patterns = [
            r'采购计划编号[：:]\s*([A-Z0-9]{2,}-[0-9]{4}-[0-9]{5,})',
            r'采购计划编号[：:\s]*([A-Z0-9]{5,}[-/][0-9]{4}[-/][0-9]{5,})',
        ]
        for pattern in plan_code_patterns:
            m = re.search(pattern, text)
            if m:
                fields.append(FieldConfidence(
                    field='plan_code',
                    value=m.group(1).strip(),
                    confidence=0.95,
                ))
                break

        # 5b. 采购项目编号 — regex: HZJJ-2025118号
        project_code_patterns = [
            r'采购项目编号[：:]\s*([A-Z0-9]+[-_]?\d+号?)',
            r'项目编号[：:]\s*([A-Z0-9]+[-_]?\d+号?)',
            r'项目编号[：:\s]*([A-Z0-9]{4,}[-_]?\d{4,}号?)',
        ]
        for pattern in project_code_patterns:
            m = re.search(pattern, text)
            if m:
                val = m.group(1).strip()
                # Skip if it looks like a budget amount or phone number
                if not re.match(r'^\d{6,}$', val) and '电话' not in val[:6]:
                    fields.append(FieldConfidence(
                        field='agency_project_code',
                        value=val,
                        confidence=0.90,
                    ))
                    break

        # 5c. Project type — service/goods/engineering
        if '服务' in text or '餐饮' in text or '配送' in text:
            fields.append(FieldConfidence(
                field='project_type',
                value='service',
                confidence=0.85,
            ))
        elif '货物' in text or '设备' in text or '材料' in text:
            fields.append(FieldConfidence(
                field='project_type',
                value='goods',
                confidence=0.80,
            ))
        elif '工程' in text or '施工' in text or '建设' in text:
            fields.append(FieldConfidence(
                field='project_type',
                value='engineering',
                confidence=0.80,
            ))

        # 6. Bid open date — look for date fields with many label patterns
        date_labels = [
            '提交投标文件截止时间和开标时间：',
            '开标时间：',
            '投标截止时间：',
            '开标日期：',
            '投标截止日期：',
            '提交投标文件截止时间：',
            '递交投标文件截止时间：',
            '投标文件递交截止时间：',
            '截标时间：',
            '截标日期：',
            '投标文件提交截止时间：',
            '递交投标文件截止时间：',
            '开标时间（北京时间）：',
            '投标截止时间（北京时间）：',
            '提交投标文件的截止时间：',
            '投标文件递交截止时间（北京时间）：',
        ]
        date_val = ''
        for label in date_labels:
            date_val = get_field_value(label)
            if date_val:
                break
        if date_val:
            parsed = parse_ocr_date(date_val)
            if parsed:
                fields.append(FieldConfidence(
                    field='bid_open_date',
                    value=str(parsed),
                    confidence=0.75,
                ))

        return fields

    def extract_qualification_requirements(self, full_text: str) -> list[dict]:
        """Extract qualification requirements from tender PDF text using LLM.

        Delegates to extract_qualifications_with_llm() which calls DeepSeek
        to perform semantic extraction of mandatory qualification requirements.

        Args:
            full_text: Full text extracted from all PDF pages.

        Returns:
            List of dicts with 'cert_code', 'cert_name', and 'is_mandatory' keys.
        """
        try:
            return extract_qualifications_with_llm(full_text)
        except Exception as e:
            logger.error(f"LLM qualification extraction failed: {e}")
            # Fallback: return empty list (don't use keyword hack as fallback)
            return []

    def _extract_qualifications_from_pdf(self, pdf_path: str) -> list[dict]:
        """Extract qualification requirements directly from a PDF file.

        Used for image-based PDFs where _process_text_pdf is not called,
        but we still need to extract qualification requirements from the
        text content of the PDF.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of requirement dicts.
        """
        doc = fitz.open(str(pdf_path))
        try:
            all_pages_text = []
            for page_num in range(min(10, len(doc))):
                text = doc[page_num].get_text()
                if text.strip():
                    all_pages_text.append(text)
            full_text = "\n".join(all_pages_text)
        finally:
            doc.close()

        return self.extract_qualification_requirements(full_text)

    def _extract_plan_codes_from_text(self, full_text: str) -> tuple[Optional[str], Optional[str]]:
        """Extract 采购计划编号 and 采购项目编号 from full PDF text using regex.

        Patterns observed in real tender documents:
          - 采购计划编号: 441301-2025-03605  (4-6 digit org code - year - 5-digit sequence)
          - 采购项目编号: HZJJ-2025118号     (alphabetic prefix + year + numeric + 号)

        Args:
            full_text: Full merged text from all PDF pages.

        Returns:
            Tuple of (plan_code, agency_project_code) — either may be None.
        """
        plan_code = None
        agency_project_code = None

        # Remove spaces between Chinese characters (OCR artifact) before regex
        collapsed = re.sub(r' (?=[\u4e00-\u9fff])', '', full_text)

        # 采购计划编号 patterns
        plan_patterns = [
            # Most common: 441301-2025-03605
            r'采购计划编号[：:\s]*([A-Z0-9]{4,}-[0-9]{4}-[0-9]{5,})',
            # Variant: separate org code with dash: 441301 - 2025 - 03605
            r'采购计划编号[：:\s]*([0-9]{4,})\s*[-－]\s*([0-9]{4})\s*[-－]\s*([0-9]{5,})',
        ]
        for pattern in plan_patterns:
            m = re.search(pattern, collapsed)
            if m:
                if len(m.groups()) == 3:
                    # Three-part pattern: reconstruct with dashes
                    plan_code = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                else:
                    plan_code = m.group(1).strip()
                break

        # 采购项目编号 patterns (项目编号 as fallback label)
        project_patterns = [
            # HZJJ-2025118号 or HZJJ-2025118
            r'采购项目编号[：:\s]*([A-Z]{2,}[-_]?[A-Z0-9]+[-_]?[0-9]{4,}号?)',
            # 项目编号 (generic, less specific but catches more formats)
            r'(?<!采购)项目编号[：:\s]*([A-Z0-9]{4,}[-_]?[0-9]{3,}号?)',
        ]
        for pattern in project_patterns:
            m = re.search(pattern, collapsed)
            if m:
                val = m.group(1).strip()
                # Skip if purely numeric (too generic / budget-like)
                if not re.match(r'^[0-9]{6,}$', val) and '电话' not in val[:8]:
                    agency_project_code = val
                    break

        return plan_code, agency_project_code

    def _extract_plan_codes_from_pdf(self, pdf_path: str) -> tuple[Optional[str], Optional[str]]:
        """Extract plan codes from a PDF file (for image-based PDFs).

        Opens the PDF and extracts text from first 10 pages, then delegates
        to _extract_plan_codes_from_text.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Tuple of (plan_code, agency_project_code).
        """
        doc = fitz.open(str(pdf_path))
        try:
            parts = []
            for page_num in range(min(10, len(doc))):
                text = doc[page_num].get_text()
                if text.strip():
                    parts.append(text)
            full_text = "\n".join(parts)
        finally:
            doc.close()
        return self._extract_plan_codes_from_text(full_text)

