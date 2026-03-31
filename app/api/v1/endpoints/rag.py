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
    """
    # Verify project exists
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Chunk the document
    chunker = DocumentChunker(chunk_size=data.chunk_size)
    chunk_nodes = chunker.chunk(text=data.content, metadata=data.metadata)

    if not chunk_nodes:
        raise HTTPException(
            status_code=400,
            detail="Document produced no chunks (empty or whitespace content)"
        )

    # Embed and store
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
        )
        db.add(chunk)
        db.flush()  # get the ID
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
    """
    # Verify project exists
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Build components
    embedder = create_embedder()
    retriever = DocumentRetriever(db, embedder)
    llm = get_llm()  # respects USE_MOCK_LLM env var
    prompt_builder = TechProposalPromptBuilder()
    generator = TechProposalGenerator(
        db=db,
        retriever=retriever,
        llm=llm,
        prompt_builder=prompt_builder,
    )

    # Determine top_k by mode
    top_k = data.top_k

    try:
        result = generator.generate_section(
            project_id=project_id,
            section_name=data.section_name,
            generation_mode=data.generation_mode,
            insider_notes=data.insider_notes,
            top_k=top_k,
        )
    except ValueError as e:
        # GUIDED mode without insider_notes, or other validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")

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
    Retrieve all previously generated sections for a project.
    Returns sections from the latest TechProposalTask that have generated content.
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Get the latest tech proposal task for this project
    task = db.query(TechProposalTask).filter(
        TechProposalTask.project_id == project_id
    ).order_by(TechProposalTask.id.desc()).first()

    if not task or not task.generated_content:
        return ResponseWrapper(data=GetSectionsResponse(
            project_id=project_id,
            sections=[],
        ).model_dump())

    # generated_content is a dict: { section_name: { content, mode, timestamp } }
    sections = []
    for section_name, data in task.generated_content.items():
        sections.append(SectionData(
            section_name=section_name,
            content=data.get('content', ''),
            mode=data.get('mode', task.generation_mode),
            generation_timestamp=data.get('timestamp', ''),
        ))

    return ResponseWrapper(data=GetSectionsResponse(
        project_id=project_id,
        sections=sections,
    ).model_dump())
