"""Week 3 RAG API endpoints — document embedding and section generation."""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.week3 import (
    EmbedDocumentRequest,
    EmbedDocumentResponse,
    ChunkInfo,
    GenerateSectionRequest,
    GeneratedSectionResponse,
    GetSectionsResponse,
    SectionData,
    SectionUpsertRequest,
    SectionUpsertResponse,
    TechProposalTaskResponse,
    TechProposalTaskStatusUpdateRequest,
)
from app.schemas.common import ResponseWrapper
from app.core.week3_rag.text_chunker import DocumentChunker
from app.core.week3_rag.embedder import create_embedder, MockEmbedder
from app.core.week3_rag.retriever import DocumentRetriever
from app.core.week3_rag.prompt_builder import TechProposalPromptBuilder
from app.core.week3_rag.llm_mock import get_llm
from app.core.week3_rag.generator import TechProposalGenerator
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.project import Project
from app.models.project_section import ProjectSection
from app.models.tech_proposal import TechProposalTask


router = APIRouter(prefix="/api/v1/projects", tags=["rag"])


# ─── POST /api/v1/projects/{project_id}/documents/embed ─────────────────────

@router.post("/{project_id}/documents/embed")
def embed_document(
    project_id: int,
    data: EmbedDocumentRequest,
    db: Session = Depends(get_db),
):
    """
    Chunk a document and store embedded chunks in knowledge_chunks table.

    Synchronous operation — chunks and embeds the provided content immediately.

    w015: Now writes historical asset RAG metadata (win_signal, scoring_dimension_tags,
    region_tags, project_type_tags, etc.) when provided.
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    chunker = DocumentChunker(chunk_size=data.chunk_size)
    chunk_nodes = chunker.chunk(text=data.content, metadata=data.metadata)

    if not chunk_nodes:
        raise HTTPException(
            status_code=400,
            detail="Document produced no chunks (empty or whitespace content)"
        )

    embedder = create_embedder()
    stored_chunks = []
    for i, node in enumerate(chunk_nodes):
        vec = embedder.embed_text(node.text)
        chunk = KnowledgeChunk(
            chunk_type=data.chunk_type,
            content=node.text,
            content_vector=json.dumps(vec),
            chunk_metadata=node.metadata,
            source_project_id=project_id,
            is_deprecated=False,
            # w015: historical asset RAG metadata
            source_type=data.source_type,
            source_id=data.source_id,
            source_label=data.source_label,
            win_signal=data.win_signal,
            scoring_dimension_tags=data.scoring_dimension_tags,
            region_tags=data.region_tags,
            project_type_tags=data.project_type_tags,
            is_price_sensitive=data.is_price_sensitive,
        )
        db.add(chunk)
        db.flush()
        stored_chunks.append(ChunkInfo(
            chunk_id=chunk.id,
            chunk_index=i,
            char_length=node.char_length,
            chunk_type=data.chunk_type,
        ))

    db.commit()

    return ResponseWrapper(data=EmbedDocumentResponse(
        project_id=project_id,
        chunks_stored=len(stored_chunks),
        chunks=stored_chunks,
    ).model_dump())


# ─── POST /api/v1/projects/{project_id}/generate-section ─────────────────────

@router.post("/{project_id}/generate-section")
def generate_section(
    project_id: int,
    data: GenerateSectionRequest,
    db: Session = Depends(get_db),
):
    """
    Generate a single tech proposal section using the RAG pipeline.

    - AUTO: standardized, compliant, no insider_notes
    - GUIDED: differentiated, requires insider_notes
    - DUAL_TRACK_RAG: when use_dual_track_rag=True, injects positive/negative
      historical samples (win_signal filtered) into the prompt context
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    embedder = create_embedder()
    retriever = DocumentRetriever(db, embedder)
    llm = get_llm()
    prompt_builder = TechProposalPromptBuilder()
    generator = TechProposalGenerator(
        db=db,
        retriever=retriever,
        llm=llm,
        prompt_builder=prompt_builder,
    )

    try:
        result = generator.generate_section(
            project_id=project_id,
            section_name=data.section_name,
            generation_mode=data.generation_mode,
            insider_notes=data.insider_notes,
            top_k=data.top_k,
            # w015/w018: dual-track RAG parameters
            scoring_dimension_tags=data.scoring_dimension_tags,
            region_tags=data.region_tags,
            use_dual_track_rag=data.use_dual_track_rag,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"大模型服务异常：{e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"技术标生成失败：{e}")

    return ResponseWrapper(data=GeneratedSectionResponse(
        project_id=project_id,
        section_name=result.section_name,
        content=result.content,
        mode=result.mode,
        token_usage=result.token_usage or {},
        source_chunk_count=len(result.source_chunks),
        generation_timestamp=result.generation_timestamp,
    ).model_dump())


# ─── GET /api/v1/projects/{project_id}/sections ─────────────────────────────────

@router.get("/{project_id}/sections")
def get_sections(project_id: int, db: Session = Depends(get_db)):
    """
    Retrieve all generated sections for a project.

    Read path (priority order):
    1. ProjectSection table (authoritative — new storage, 2026-04-01+)
    2. TechProposalTask.generated_content JSON (legacy fallback for old projects)
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    db_sections = (
        db.query(ProjectSection)
        .filter(ProjectSection.project_id == project_id)
        .all()
    )
    if db_sections:
        return ResponseWrapper(data=GetSectionsResponse(
            project_id=project_id,
            sections=[
                SectionData(
                    section_name=sec.section_name,
                    content=sec.content or '',
                    mode='auto',
                    generation_timestamp=sec.updated_at.isoformat() if sec.updated_at else '',
                )
                for sec in db_sections
            ],
        ).model_dump())

    task = (
        db.query(TechProposalTask)
        .filter(TechProposalTask.project_id == project_id)
        .order_by(TechProposalTask.id.desc())
        .first()
    )
    if not task or not task.generated_content:
        return ResponseWrapper(data=GetSectionsResponse(
            project_id=project_id,
            sections=[],
        ).model_dump())

    sections = []
    content = task.generated_content
    if isinstance(content, dict):
        if 'sections' in content:
            for sec in content['sections']:
                sections.append(SectionData(
                    section_name=sec.get('section_name', sec.get('title', '')),
                    content=sec.get('content', ''),
                    mode=sec.get('mode', task.generation_mode or 'auto'),
                    generation_timestamp=sec.get('timestamp', ''),
                ))
        else:
            for section_name, data in content.items():
                sections.append(SectionData(
                    section_name=section_name,
                    content=data.get('content', ''),
                    mode=data.get('mode', task.generation_mode or 'auto'),
                    generation_timestamp=data.get('timestamp', ''),
                ))

    return ResponseWrapper(data=GetSectionsResponse(
        project_id=project_id,
        sections=sections,
    ).model_dump())


# ─── PUT /api/v1/projects/{project_id}/sections/{section_name} ─────────────────

@router.put("/{project_id}/sections/{section_name}")
def upsert_section(
    project_id: int,
    section_name: str,
    data: SectionUpsertRequest,
    db: Session = Depends(get_db),
):
    """
    Upsert a single section to ProjectSection (authoritative storage).

    Called after LLM generation completes or when user clicks re-generate.
    Uses INSERT ... ON CONFLICT DO UPDATE to replace content idempotently.
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    existing = (
        db.query(ProjectSection)
        .filter(
            ProjectSection.project_id == project_id,
            ProjectSection.section_name == section_name,
        )
        .first()
    )

    now = datetime.now()
    if existing:
        existing.content = data.content
        existing.updated_at = now
        upserted = False
    else:
        existing = ProjectSection(
            project_id=project_id,
            section_name=section_name,
            content=data.content,
            created_at=now,
            updated_at=now,
        )
        db.add(existing)
        upserted = True

    db.commit()
    db.refresh(existing)

    return ResponseWrapper(data=SectionUpsertResponse(
        project_id=project_id,
        section_name=section_name,
        content=data.content,
        upserted=upserted,
        saved_at=existing.updated_at.isoformat() if existing.updated_at else now.isoformat(),
    ).model_dump())


# ─── GET /api/v1/projects/{project_id}/tech-proposal/current ─────────────────

@router.get("/{project_id}/tech-proposal/current")
def get_current_tech_proposal(project_id: int, db: Session = Depends(get_db)):
    """
    Get the most recent TechProposalTask for a project.

    Returns the newest TechProposalTask ordered by id DESC, or 404 if none exists.
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    task = (
        db.query(TechProposalTask)
        .filter(TechProposalTask.project_id == project_id)
        .order_by(TechProposalTask.id.desc())
        .first()
    )

    if not task:
        raise HTTPException(status_code=404, detail=f"No TechProposalTask found for project {project_id}")

    return ResponseWrapper(data=TechProposalTaskResponse(
        id=task.id,
        project_id=task.project_id,
        generation_mode=task.generation_mode,
        input_config=task.input_config or {},
        generated_content=task.generated_content,
        final_content=task.final_content,
        editor_version=task.editor_version,
        status=task.status,
        created_by=task.created_by,
        confirmed_at=task.confirmed_at.isoformat() if task.confirmed_at else None,
        confirmed_by=task.confirmed_by,
        created_at=task.created_at.isoformat() if task.created_at else None,
        updated_at=task.updated_at.isoformat() if task.updated_at else None,
    ).model_dump())


# ─── PUT /api/v1/tech-proposal-tasks/{id}/status ─────────────────────────────

@router.put("/tech-proposal-tasks/{task_id}/status")
def update_tech_proposal_status(
    task_id: int,
    data: TechProposalTaskStatusUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    Update the status of a TechProposalTask.

    Valid statuses: 'generating', 'generated', 'confirmed', 'rejected'
    When status is set to 'confirmed', confirmed_at is also set to current time.
    """
    task = db.get(TechProposalTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"TechProposalTask {task_id} not found")

    task.status = data.status

    if data.status == "confirmed":
        task.confirmed_at = datetime.now()

    db.commit()
    db.refresh(task)

    return ResponseWrapper(data=TechProposalTaskResponse(
        id=task.id,
        project_id=task.project_id,
        generation_mode=task.generation_mode,
        input_config=task.input_config or {},
        generated_content=task.generated_content,
        final_content=task.final_content,
        editor_version=task.editor_version,
        status=task.status,
        created_by=task.created_by,
        confirmed_at=task.confirmed_at.isoformat() if task.confirmed_at else None,
        confirmed_by=task.confirmed_by,
        created_at=task.created_at.isoformat() if task.created_at else None,
        updated_at=task.updated_at.isoformat() if task.updated_at else None,
    ).model_dump())
