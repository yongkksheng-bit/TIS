"""Qualification Exact Matcher - Week 2 Core Engine.

R1 Life-or-Death Rules:
- Single Source of Truth: ONLY validated (is_validated=True) OCR records
- Exact match ONLY: no fuzzy matching
- Expiry check: valid_until MUST cover bid_open_date
- Exclude keyword safeguard: final validation even on matched certs
"""
import json
from typing import Optional
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_


class QualificationMatcher:
    """
    Week 2 core: Exact qualification matching between:
    - Tender document requirements (cert_code + is_mandatory)
    - Week 1 validated OCR extractions (Single Source of Truth)

    ABSOLUTE RULE: Only reads is_validated=True records. Never re-parse.
    """

    def __init__(self, db: Session, project_id: int):
        self.db = db
        self.project_id = project_id

    def exact_match_evaluation(self) -> dict:
        """
        Execute exact qualification matching.

        Returns:
            qualification_match_score: int (0-100)
            missing_mandatory_certs: list[dict] (reason='missing' or 'expired')
            missing_optional_certs: list[dict]
            matched_certs: list[dict]
            is_qualification_pass: bool
        """
        # Get validated OCR cert extractions (Single Source of Truth)
        bid_certs = self._get_validated_cert_extractions()

        # Get tender requirements
        tender_reqs = self._get_tender_requirements()

        # Evaluate each requirement
        fatal_missing = []  # missing OR expired mandatory certs
        optional_missing = []
        matched_list = []

        for req in tender_reqs:
            cert_code = req['cert_code']
            is_mandatory = req.get('is_mandatory', False)
            std_cert = req.get('standard_cert')

            # Step 1: Find matching validated OCR extraction
            matched_extraction = self._find_matching_extraction(bid_certs, cert_code)

            if matched_extraction is None:
                # Cert not found in OCR → missing
                if is_mandatory:
                    fatal_missing.append({
                        'cert_code': cert_code,
                        'cert_name': std_cert.cert_full_name if std_cert else cert_code,
                        'reason': 'missing',
                        'severity': 'fatal'
                    })
                else:
                    optional_missing.append(cert_code)
                continue

            # Step 2: Check exclude keywords (final safeguard)
            cert_text = matched_extraction.normalized_value or matched_extraction.field_value or ''
            if std_cert and self._fails_exclude_keyword_check(cert_text, std_cert):
                # Wrong cert confirmed by exclude keyword → treat as missing
                if is_mandatory:
                    fatal_missing.append({
                        'cert_code': cert_code,
                        'cert_name': std_cert.cert_full_name if std_cert else cert_code,
                        'reason': 'wrong_cert_blocked_by_exclude',
                        'severity': 'fatal'
                    })
                else:
                    optional_missing.append(cert_code)
                continue

            # Step 3: Check validity (expiry date)
            validity = self._check_cert_validity(
                matched_extraction.normalized_value,
                matched_extraction.raw_text
            )

            if validity['status'] == 'expired':
                if is_mandatory:
                    fatal_missing.append({
                        'cert_code': cert_code,
                        'cert_name': std_cert.cert_full_name if std_cert else cert_code,
                        'reason': 'expired',
                        'valid_until': validity.get('valid_until'),
                        'severity': 'fatal'
                    })
                # Even if optional, expired cert is not added to matched
                continue
            elif validity['status'] == 'expiring_soon':
                # Add to matched but also to warning (handled in Week 2 report)
                matched_list.append({
                    'cert_code': cert_code,
                    'cert_name': std_cert.cert_full_name if std_cert else cert_code,
                    'valid_until': validity.get('valid_until'),
                    'status': 'valid_but_expiring_soon',
                    'evidence_image_id': matched_extraction.image_id
                })
            else:
                matched_list.append({
                    'cert_code': cert_code,
                    'cert_name': std_cert.cert_full_name if std_cert else cert_code,
                    'valid_until': validity.get('valid_until'),
                    'status': 'valid',
                    'evidence_image_id': matched_extraction.image_id
                })

        # Calculate score
        total_mandatory = len([r for r in tender_reqs if r.get('is_mandatory')])
        matched_mandatory = total_mandatory - len([m for m in fatal_missing if m['reason'] == 'missing'])
        score = int((matched_mandatory / total_mandatory) * 100) if total_mandatory > 0 else 100

        # Determine pass/fail
        has_fatal = any(m['reason'] in ['missing', 'expired', 'wrong_cert_blocked_by_exclude'] for m in fatal_missing)

        return {
            'qualification_match_score': score,
            'missing_mandatory_certs': fatal_missing,
            'missing_optional_certs': optional_missing,
            'matched_certs': matched_list,
            'is_qualification_pass': not has_fatal
        }

    def _get_validated_cert_extractions(self) -> list:
        """Get all validated OCR cert extractions (Single Source of Truth)."""
        from app.models.ocr import OcrExtraction
        return self.db.query(OcrExtraction).filter(
            OcrExtraction.project_id == self.project_id,
            OcrExtraction.is_validated == True,
            OcrExtraction.standard_cert_id.isnot(None)
        ).all()

    def _get_tender_requirements(self) -> list:
        """Get qualification requirements from tender document."""
        from app.models.document import TenderDocument
        from app.models.standard import StandardCertification

        tender = self.db.query(TenderDocument).filter_by(project_id=self.project_id).first()
        if not tender or not tender.extracted_data:
            return []

        requirements = tender.extracted_data.get('qualification_requirements', [])
        # Enrich with StandardCertification objects
        enriched = []
        for req in requirements:
            cert = self.db.query(StandardCertification).filter_by(cert_code=req.get('cert_code')).first()
            req['standard_cert'] = cert
            enriched.append(req)
        return enriched

    def _find_matching_extraction(self, bid_certs, cert_code: str):
        """Find OCR extraction matching this cert_code."""
        for ext in bid_certs:
            if ext.standard_cert_id is not None:
                # Check if standard_cert_id matches the required cert
                from app.models.standard import StandardCertification
                std_cert = self.db.get(StandardCertification, ext.standard_cert_id)
                if std_cert and std_cert.cert_code == cert_code:
                    return ext
        return None

    def _fails_exclude_keyword_check(self, cert_text: str, std_cert) -> bool:
        """Check if cert text contains any exclude keyword."""
        if not std_cert:
            return False
        exclude = std_cert.exclude_keywords
        if isinstance(exclude, str):
            exclude = json.loads(exclude)
        if not exclude:
            return False
        text = cert_text.lower()
        for kw in exclude:
            if kw.lower() in text:
                return True
        return False

    def _check_cert_validity(self, normalized_value: str, raw_text: str) -> dict:
        """
        Check if cert validity covers bid open date.

        Returns dict with:
            status: 'valid' | 'expired' | 'expiring_soon' | 'unknown'
            valid_until: date string or None
        """
        from app.models.project import Project

        # Get bid open date
        project = self.db.get(Project, self.project_id)
        if not project or not project.bid_open_date:
            return {'status': 'unknown'}

        bid_open_date = project.bid_open_date
        if isinstance(bid_open_date, datetime):
            bid_open_date = bid_open_date.date()

        # Extract valid_until from normalized_value or raw_text
        valid_until = self._extract_date(normalized_value or raw_text or '')
        if not valid_until:
            return {'status': 'unknown', 'valid_until': None}

        if valid_until < bid_open_date:
            return {'status': 'expired', 'valid_until': str(valid_until), 'days_past': (bid_open_date - valid_until).days}

        if valid_until < bid_open_date + timedelta(days=90):
            return {'status': 'expiring_soon', 'valid_until': str(valid_until), 'days_until_expire': (valid_until - bid_open_date).days}

        return {'status': 'valid', 'valid_until': str(valid_until), 'days_valid': (valid_until - bid_open_date).days}

    def _extract_date(self, text: str) -> Optional[date]:
        """Extract YYYY-MM-DD date from text."""
        import re
        if not text:
            return None
        # Try YYYY-MM-DD format
        m = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', text)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
        # Try YYYY/MM/DD
        m = re.search(r'(\d{4})/(\d{1,2})/(\d{1,2})', text)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
        return None