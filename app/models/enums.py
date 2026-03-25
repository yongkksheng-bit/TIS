import enum


class ProjectStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    EVALUATING = "evaluating"
    EVALUATION_READY = "evaluation_ready"
    APPROVED_BY_SPECIALIST = "approved_by_specialist"
    REJECTED_BY_SPECIALIST = "rejected_by_specialist"
    TERMINATED_BY_BOSS = "terminated_by_boss"
    GENERATING_DOCUMENTS = "generating_documents"
    AWAITING_PRICING = "awaiting_pricing"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"


class GenerationMode(str, enum.Enum):
    AUTO = "auto"        # 无关系：全自动RAG
    GUIDED = "guided"    # 有关系：引导模式


class OwnerType(str, enum.Enum):
    SCHOOL = "school"
    GOVERNMENT = "government"
    HOSPITAL = "hospital"
    ENTERPRISE = "enterprise"


class ParsingStatus(str, enum.Enum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    OCR_PROCESSING = "ocr_processing"
    STRUCTURING = "structuring"
    COMPLETED = "completed"
    FAILED = "failed"


class DocType(str, enum.Enum):
    QUALIFICATION = "qualification"
    TECHNICAL = "technical"
    BUSINESS = "business"
    PRICING = "pricing"


class ImageType(str, enum.Enum):
    BUSINESS_LICENSE = "business_license"
    CERTIFICATION = "certification"
    CONTRACT = "contract"
    ID_CARD = "id_card"
    OTHER = "other"


class OcrStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class OcrFieldName(str, enum.Enum):
    CERT_NAME = "cert_name"
    CERT_NUMBER = "cert_number"
    ISSUING_AUTHORITY = "issuing_authority"
    VALID_FROM = "valid_from"
    VALID_UNTIL = "valid_until"
    BUSINESS_SCOPE = "business_scope"
    COMPANY_NAME = "company_name"
    CREDIT_CODE = "credit_code"
    LEGAL_REPRESENTATIVE = "legal_representative"
    PERSON_NAME = "person_name"
    PERSON_ID = "person_id"
    CONTRACT_AMOUNT = "contract_amount"
    CONTRACT_DATE = "contract_date"


class CertCategory(str, enum.Enum):
    FOOD = "food"
    CONSTRUCTION = "construction"
    ISO = "iso"
    PERSONNEL = "personnel"


class TimeUrgencyLevel(str, enum.Enum):
    EXPIRED = "expired"    # < 0 days
    URGENT = "urgent"      # 1-3 days
    TIGHT = "tight"        # 4-7 days
    NORMAL = "normal"      # 8-15 days
    RELAXED = "relaxed"    # > 15 days

class RiskLevel(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class Recommendation(str, enum.Enum):
    WORTH_BIDDING = "worth_bidding"
    ABANDON = "abandon"
    CONDITIONAL = "conditional"

class ApprovalAction(str, enum.Enum):
    SPECIALIST_WORTHY = "specialist_worthy"
    SPECIALIST_UNWORTHY = "specialist_unworthy"
    BOSS_OVERRIDE_TERMINATE = "boss_override_terminate"
    BOSS_OVERRIDE_REVIVE = "boss_override_revive"
    BOSS_CONFIRM_SPECIALIST = "boss_confirm_specialist"

class RelationshipLevel(str, enum.Enum):
    NONE = "none"
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"

class CostConfidence(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
