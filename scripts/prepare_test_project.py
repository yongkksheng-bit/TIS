"""
Prepare a complete test project in the database for E2E UI testing.
Creates project with full OCR data so confirmation page works properly.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.project import Project
from app.models.document import DocumentImage, OcrExtraction, BidDocument
from app.models.enums import ProjectStatus
from datetime import datetime

DATABASE_URL = "postgresql://postgres:Syk0215@localhost:5433/canteen_system"

def main():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # Clean up any existing test projects
        existing = db.query(Project).filter_by(
            project_name="惠州食堂投标项目（自动化测试）"
        ).first()
        if existing:
            db.delete(existing)
            db.commit()
            print(f"[DB] Deleted existing test project ID {existing.id}")

        # Create project
        project = Project(
            project_name="惠州食堂投标项目（自动化测试）",
            owner_unit="惠州市人民政府机关事务管理局",
            project_type="食堂承包服务",
            region="广东省惠州市",
            budget_amount=8000000.0,
            bid_open_date=datetime(2026, 4, 15, 9, 30),
            status=ProjectStatus.PARSED,
            relationship_flag=False,
            relation_identifier="not_involved",
        )
        db.add(project)
        db.flush()
        project_id = project.id
        print(f"[DB] Created project ID: {project_id}")

        # Create BidDocument
        bid_doc = BidDocument(
            project_id=project_id,
            doc_type="business",
            file_path="test_fixtures/huizhou_tender.pdf",
        )
        db.add(bid_doc)
        db.flush()
        doc_id = bid_doc.id
        print(f"[DB] Created BidDocument ID: {doc_id}")

        # Create DocumentImage (text page reference)
        pdf_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data/test_documents/huizhou_tender.pdf"
        )
        doc_image = DocumentImage(
            document_id=doc_id,
            project_id=project_id,
            image_path=pdf_path if os.path.exists(pdf_path) else "test_fixtures/huizhou_tender.pdf",
            page_number=1,
            image_hash="abcd1234efgh",
            image_type="text_page",
            ocr_status="success",
        )
        db.add(doc_image)
        db.flush()
        img_id = doc_image.id
        print(f"[DB] Created DocumentImage ID: {img_id}")

        # Create OCR extractions with realistic data
        extractions_data = [
            ("project_name", "惠州市政府机关食堂承包服务采购项目", "惠州市政府机关食堂承包服务采购项目", 0.95),
            ("owner_unit", "惠州市人民政府机关事务管理局", "惠州市人民政府机关事务管理局", 0.95),
            ("budget_amount", "8000000.00元", "8000000", 0.90),
            ("bid_open_date", "2026年4月15日 09:30", "2026-04-15", 0.95),
            ("region", "广东省惠州市", "广东省惠州市", 0.85),
        ]

        for field_name, field_value, normalized, confidence in extractions_data:
            ext = OcrExtraction(
                image_id=img_id,
                project_id=project_id,
                field_name=field_name,
                field_value=field_value,
                normalized_value=normalized,
                confidence_score=confidence,
                is_validated=False,
            )
            db.add(ext)

        db.commit()
        print(f"\n[SUCCESS] Test project {project_id} ready!")
        print(f"  Status: parsed (ready for confirmation)")
        print(f"  Owner: {project.owner_unit}")
        print(f"  Bid open: {project.bid_open_date}")
        print(f"  OCR extractions: {len(extractions_data)} fields")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    from datetime import datetime
    main()
