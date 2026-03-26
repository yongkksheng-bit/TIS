"""TechProposalPromptBuilder — mode-aware system + user prompts for AUTO/GUIDED."""
from typing import Optional
from app.schemas.rag import ChunkNode


# ─── Strategic keywords for each mode ────────────────────────────────────────
AUTO_KEYWORDS = [
    "标准化", "合规要求", "低成本", "高效率", "规范操作", "质量保证",
    "流程规范", "风险可控", "最佳实践", "统一标准"
]

GUIDED_KEYWORDS = [
    "差异化竞争", "量身定制", "高溢价", "竞争优势", "精准匹配",
    "超预期", "个性化", "策略性", "核心竞争力", "价值最大化"
]

AUTO_SYSTEM_PROMPT_TEMPLATE = """你是一位专业的招投标技术标撰写专家。

核心原则：
- 严格遵守《{project_type}领域招投标规范》
- 方案必须标准化、结构化、可量化评审
- 突出合规性、规范性、质量保证体系
- 措辞严谨专业，符合评审专家阅读习惯

输出要求：
- 语言简洁专业，避免空洞套话
- 数据指标具体可验证
- 响应所有评分项，证据链完整
"""

GUIDED_SYSTEM_PROMPT_TEMPLATE = """你是一位资深招投标顾问，擅长为客户量身定制高溢价技术标方案。

核心优势构建：
- 深入挖掘客户需求的差异化要点
- 突出竞争优势，构建竞争壁垒
- 方案需体现战略高度和落地可行性的平衡
- 措辞精准有力，说服力强，让评审眼前一亮

{mode_guidance}
"""

GUIDANCE_WITH_NOTES = """【内幕要点】（必须全部采纳进方案）
{insider_notes}

要求：将以上内幕要点有机融入各章节，确保方案体现这些独家竞争优势。"""

USER_PROMPT_TEMPLATE = """## 项目信息
- 项目名称：{project_name}
- 业主单位：{owner_unit}
- 业务类型：{project_type}
- 地区：{region}
- 预算：{budget_amount}
- 投标截止：{bid_open_date}

## 待撰写章节
目标章节：{target_section}

## 参考知识库
<reference_documents>
{context_chunks}
</reference_documents>

## 输出要求
请基于以上参考知识库，为上述章节撰写专业、完整、有竞争力的技术标内容。响应所有评分项，提供具体数据和实施路径。"""


class TechProposalPromptBuilder:
    """
    Builds system prompts and user prompts for AUTO vs GUIDED generation modes.

    AUTO mode: standardised, compliant, efficient — no insider_notes
    GUIDED mode: differentiated, tailored, insider-notes-driven — REQUIRES insider_notes
    """

    def build_system_prompt(
        self,
        generation_mode: str,
        insider_notes: Optional[str] = None,
        project_type: str = "通用",
    ) -> str:
        """
        Build mode-specific system prompt.

        Args:
            generation_mode: 'auto' or 'guided'
            insider_notes: Required for GUIDED mode, ignored for AUTO mode
            project_type: Type of project for domain adaptation

        Returns:
            System prompt string

        Raises:
            ValueError: If generation_mode='guided' but insider_notes is None/empty
        """
        mode = generation_mode.lower()

        if mode == "auto":
            return AUTO_SYSTEM_PROMPT_TEMPLATE.format(project_type=project_type)

        elif mode == "guided":
            if not insider_notes or not insider_notes.strip():
                raise ValueError("GUIDED mode requires insider_notes")

            guidance = GUIDANCE_WITH_NOTES.format(insider_notes=insider_notes)
            return GUIDED_SYSTEM_PROMPT_TEMPLATE.format(
                project_type=project_type,
                mode_guidance=guidance
            )

        else:
            raise ValueError(f"Unknown generation_mode: {generation_mode}. Use 'auto' or 'guided'.")

    def build_user_prompt(
        self,
        project_info: dict,
        context_chunks: list[ChunkNode],
        target_section: str,
    ) -> str:
        """
        Build user prompt with project info and context chunks in XML tags.

        Args:
            project_info: dict with project_name, owner_unit, project_type, region,
                         budget_amount, bid_open_date
            context_chunks: list of ChunkNode from the retriever
            target_section: e.g. "第一章：冷链配送方案"

        Returns:
            User prompt string with XML-wrapped context chunks
        """
        # Format context chunks into XML
        chunk_texts = []
        for chunk in context_chunks:
            source_info = ""
            if chunk.metadata:
                if chunk.metadata.get("source"):
                    source_info = f" (来源: {chunk.metadata['source']})"
                elif chunk.metadata.get("chunk_type"):
                    source_info = f" (类型: {chunk.metadata['chunk_type']})"
            chunk_texts.append(f"<document>{chunk.text}{source_info}</document>")

        context_xml = "\n".join(chunk_texts)

        # Fill in project info
        bid_date = "未知"
        if project_info.get("bid_open_date"):
            bid_date = project_info["bid_open_date"]
            if hasattr(bid_date, 'strftime'):
                bid_date = bid_date.strftime("%Y-%m-%d")

        budget = project_info.get("budget_amount", "未披露")
        if budget and budget != "未披露":
            budget = f"{float(budget):,.2f}"

        return USER_PROMPT_TEMPLATE.format(
            project_name=project_info.get("project_name", "未命名项目"),
            owner_unit=project_info.get("owner_unit", "未知业主"),
            project_type=project_info.get("project_type", "通用"),
            region=project_info.get("region", "未知地区"),
            budget_amount=budget,
            bid_open_date=bid_date,
            target_section=target_section,
            context_chunks=context_xml,
        )

    def mode_keywords(self, generation_mode: str) -> list[str]:
        """Return the strategic keywords for a given mode."""
        if generation_mode.lower() == "auto":
            return AUTO_KEYWORDS
        return GUIDED_KEYWORDS
