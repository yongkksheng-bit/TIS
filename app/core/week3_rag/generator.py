"""TechProposalGenerator — RAG pipeline orchestrator for tech proposal generation."""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.core.week3_rag.retriever import DocumentRetriever
from app.core.week3_rag.embedder import MockEmbedder, create_embedder
from app.core.week3_rag.prompt_builder import TechProposalPromptBuilder
from app.core.week3_rag.llm_mock import MockDeepSeekLLM, get_llm
from app.models.tech_proposal import TechProposalTask, GenerationLog
from app.models.project import Project


class GenerationResult:
    """Structured result from section generation."""

    def __init__(
        self,
        section_name: str,
        content: str,
        source_chunks: list,
        generation_timestamp: str,
        mode: str,
        token_usage: dict | None = None,
    ):
        self.section_name = section_name
        self.content = content
        self.source_chunks = source_chunks
        self.generation_timestamp = generation_timestamp
        self.mode = mode
        self.token_usage = token_usage or {}

    def to_dict(self) -> dict:
        return {
            "section_name": self.section_name,
            "content": self.content,
            "source_chunks": self.source_chunks,
            "generation_timestamp": self.generation_timestamp,
            "mode": self.mode,
            "token_usage": self.token_usage,
        }


class TechProposalGenerator:
    """
    Main orchestrator: RAG retrieval → Prompt building → LLM generation.

    Dependencies (all injected):
    - db: Session
    - retriever: DocumentRetriever
    - embedder: BaseEmbedder
    - llm: MockDeepSeekLLM (or real client)
    - prompt_builder: TechProposalPromptBuilder
    """

    def __init__(
        self,
        db: Session,
        retriever: DocumentRetriever | None = None,
        embedder=None,
        llm=None,
        prompt_builder: TechProposalPromptBuilder | None = None,
    ):
        self.db = db
        self.retriever = retriever or DocumentRetriever(
            db, embedder or create_embedder()
        )
        self.embedder = embedder or self.retriever.embedder
        self.llm = llm or get_llm()
        self.prompt_builder = prompt_builder or TechProposalPromptBuilder()

    def generate_section(
        self,
        project_id: int,
        section_name: str,
        generation_mode: str,
        insider_notes: str | None = None,
        top_k: int = 5,
    ) -> GenerationResult:
        """
        Full pipeline: retrieve → build prompt → generate → log.

        Args:
            project_id: project to generate for (MUST be used for retrieval filter)
            section_name: e.g. "第一章：冷链配送方案"
            generation_mode: 'auto' or 'guided'
            insider_notes: required for GUIDED mode
            top_k: number of chunks to retrieve (5 for AUTO, 3 for GUIDED)

        Returns:
            GenerationResult with content and metadata

        Raises:
            ValueError: if generation_mode='guided' but insider_notes missing/empty
        """
        timestamp = datetime.utcnow().isoformat() + "Z"
        prompt_used: str | None = None
        token_usage: dict = {}

        try:
            # ─── Step 1: Build retrieval query ───────────────────────────────────
            retrieval_query = f"关于{section_name}的要求、方案和规范"

            # ─── Step 2: Retrieve top_k chunks (project_id isolation is MANDATORY) ─
            chunks = self.retriever.search(
                query=retrieval_query,
                project_id=project_id,
                top_k=top_k,
            )

            # ─── Step 3: Get project info for prompt ─────────────────────────────
            project = self.db.get(Project, project_id)
            project_info = {
                "project_name": project.project_name if project else "未知项目",
                "owner_unit": project.owner_unit if project else "未知业主",
                "project_type": project.project_type if project else "通用",
                "region": project.region if project else "未知地区",
                "budget_amount": str(project.budget_amount) if project and project.budget_amount else "未披露",
                "bid_open_date": (
                    project.bid_open_date.strftime("%Y-%m-%d")
                    if project and project.bid_open_date else "未知"
                ),
            }

            # ─── Step 4: Build prompts ────────────────────────────────────────────
            system_prompt = self.prompt_builder.build_system_prompt(
                generation_mode=generation_mode,
                insider_notes=insider_notes,
                project_type=project_info["project_type"],
            )
            user_prompt = self.prompt_builder.build_user_prompt(
                project_info=project_info,
                context_chunks=chunks,
                target_section=section_name,
            )
            prompt_used = f"{system_prompt}\n\n{user_prompt}"

            # ─── Step 5: Generate with LLM ──────────────────────────────────────
            temperature = 0.7 if generation_mode == "auto" else 0.5
            response = self.llm.generate(
                prompt=user_prompt,
                mode=generation_mode,
                insider_notes=[insider_notes] if insider_notes else None,
                temperature=temperature,
                system_prompt=system_prompt,
            )

            content = response.content
            token_usage = response.usage or {}

        except Exception as e:
            # Rollback the aborted transaction before logging
            self.db.rollback()
            # Log the failed attempt before re-raising
            self._create_generation_log(
                task_id=None,
                operation_type="generate_section",
                section_name=section_name,
                mode=generation_mode,
                prompt_used=prompt_used,
                token_usage=token_usage,
                error=str(e),
            )
            raise

        # ─── Step 6: Log successful generation ─────────────────────────────────
        self._create_generation_log(
            task_id=None,
            operation_type="generate_section",
            section_name=section_name,
            mode=generation_mode,
            prompt_used=prompt_used,
            token_usage=token_usage,
        )

        return GenerationResult(
            section_name=section_name,
            content=content,
            source_chunks=[c.to_dict() if hasattr(c, 'to_dict') else {
                "text": c.text,
                "chunk_index": c.chunk_index,
                "char_length": c.char_length,
                "metadata": c.metadata,
            } for c in chunks],
            generation_timestamp=timestamp,
            mode=generation_mode,
            token_usage=token_usage,
        )

    def _create_generation_log(
        self,
        task_id: int | None,
        operation_type: str,
        section_name: str,
        mode: str,
        prompt_used: str | None,
        token_usage: dict,
        error: str | None = None,
    ) -> None:
        """Persist generation attempt to generation_logs table."""
        log = GenerationLog(
            task_id=task_id,
            operation_type=operation_type,
            section_id=0,  # section index not tracked separately here
            prompt_used=prompt_used,
            input_tokens=token_usage.get("prompt_tokens"),
            output_tokens=token_usage.get("completion_tokens"),
            cost_usd=token_usage.get("cost_usd"),
        )
        self.db.add(log)
        self.db.commit()
