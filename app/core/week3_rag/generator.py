"""TechProposalGenerator — RAG pipeline orchestrator for tech proposal generation."""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.week3_rag.retriever import DocumentRetriever
from app.core.week3_rag.embedder import create_embedder
from app.core.week3_rag.prompt_builder import TechProposalPromptBuilder
from app.core.week3_rag.llm_mock import get_llm
from app.core.week3_rag.prompt_templates import (
    TECH_PROPOSAL_CHUNK_SYSTEM_PROMPT,
    build_chunk_context,
    build_legacy_context,
)
from app.models.tech_proposal import GenerationLog
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

    w015/w018 dual-track RAG:
    When use_dual_track_rag=True, retrieves positive (win_signal='positive')
    and negative (win_signal='negative') historical samples and injects them
    into the system prompt via build_chunk_context().
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
        # ── w015/w018: dual-track RAG parameters ─────────────────────────────
        scoring_dimension_tags: list[str] | None = None,
        region_tags: list[str] | None = None,
        use_dual_track_rag: bool = False,
    ) -> GenerationResult:
        """
        Full pipeline: retrieve → build prompt → generate → log.

        Args:
            project_id: project to generate for (MUST be used for retrieval filter)
            section_name: e.g. "第一章：冷链配送方案"
            generation_mode: 'auto' or 'guided'
            insider_notes: required for GUIDED mode
            top_k: number of active-project chunks to retrieve (5 for AUTO, 3 for GUIDED)
            scoring_dimension_tags: w015 — filter historical chunks by scoring dimensions
            region_tags: w015 — filter historical chunks by region
            use_dual_track_rag: w015 — whether to inject positive/negative historical context

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

            # ─── Step 2: Active-project RAG retrieval ───────────────────────────
            # Filters by project_id — MANDATORY isolation
            chunks = self.retriever.search(
                query=retrieval_query,
                project_id=project_id,
                top_k=top_k,
            )

            # ─── Step 3: Dual-track historical RAG retrieval (w015/w018) ──────
            # Only runs when use_dual_track_rag=True; does NOT filter by project_id
            # because historical assets are cross-project by design (hard-isolated archive)
            dual_track_context = ""
            if use_dual_track_rag:
                dual_track_context = self._build_dual_track_context(
                    query=retrieval_query,
                    scoring_dimension_tags=scoring_dimension_tags,
                    region_tags=region_tags,
                    top_k=top_k,
                )

            # ─── Step 4: Get project info for prompt ─────────────────────────────
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

            # ─── Step 5: Build system prompt ──────────────────────────────────────
            # Inject dual-track context as a prefix/suffix to the base system prompt
            system_prompt = self.prompt_builder.build_system_prompt(
                generation_mode=generation_mode,
                insider_notes=insider_notes,
                project_type=project_info["project_type"],
                dual_track_context=dual_track_context,
            )

            # ─── Step 6: Build user prompt ────────────────────────────────────────
            # Preserve legacy context format for active-project chunks (backward compat)
            if chunks and len(chunks) > 0:
                legacy_chunks = [
                    {"text": c.text, "chunk_type": c.metadata.get("source_label", "文档片段")}
                    for c in chunks
                ]
                context_str = build_legacy_context(legacy_chunks)
            else:
                context_str = "(当前无上下文参考)"

            user_prompt = self.prompt_builder.build_user_prompt(
                project_info=project_info,
                context_chunks=chunks,
                target_section=section_name,
            )
            prompt_used = f"{system_prompt}\n\n{user_prompt}"

            # ─── Step 7: Generate with LLM ──────────────────────────────────────
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
            self.db.rollback()
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

        # ─── Step 8: Log successful generation ─────────────────────────────────
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

    def _build_dual_track_context(
        self,
        query: str,
        scoring_dimension_tags: list[str] | None,
        region_tags: list[str] | None,
        top_k: int,
    ) -> str:
        """
        Retrieve positive and negative historical samples and assemble
        dual-track context string using build_chunk_context().

        Returns empty string if no historical assets exist yet (graceful degradation).
        """
        project_type = None  # could be passed through if needed

        try:
            # Retrieve up to top_k positive samples
            positive_chunks = self.retriever.retrieve_positive_samples(
                query=query,
                scoring_dimension_tags=scoring_dimension_tags,
                region_tags=region_tags,
                project_type=project_type,
                top_k=top_k,
            )

            # Retrieve up to top_k negative samples
            negative_chunks = self.retriever.retrieve_negative_samples(
                query=query,
                scoring_dimension_tags=scoring_dimension_tags,
                region_tags=region_tags,
                project_type=project_type,
                top_k=top_k,
            )

            # Convert ChunkNode objects to dicts for build_chunk_context
            def chunk_to_dict(c, win_signal: str) -> dict:
                return {
                    "text": c.text,
                    "chunk_index": c.chunk_index,
                    "win_signal": win_signal,
                    "scoring_dimension_tags": c.metadata.get("scoring_dimension_tags", []),
                    "region_tags": c.metadata.get("region_tags", []),
                    "project_type_tags": c.metadata.get("project_type_tags", []),
                    "source_label": c.metadata.get("source_label", ""),
                    "metadata": c.metadata,
                }

            all_historical = (
                [chunk_to_dict(c, "positive") for c in positive_chunks] +
                [chunk_to_dict(c, "negative") for c in negative_chunks]
            )

            if not all_historical:
                return ""

            return build_chunk_context(all_historical)

        except Exception:
            # Graceful degradation: if historical retrieval fails (e.g., no data yet),
            # return empty string and proceed without dual-track context
            return ""

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
            section_id=0,
            prompt_used=prompt_used,
            input_tokens=token_usage.get("prompt_tokens"),
            output_tokens=token_usage.get("completion_tokens"),
            cost_usd=token_usage.get("cost_usd"),
        )
        self.db.add(log)
        self.db.commit()
