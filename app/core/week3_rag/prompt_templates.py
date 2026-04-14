"""Prompt templates for dual-track RAG — win_signal='positive' vs 'negative' context."""
from typing import Optional


# ─── Dual-Track System Prompt ─────────────────────────────────────────────────

TECH_PROPOSAL_CHUNK_SYSTEM_PROMPT = """你是一位资深政府采购招投标专家，擅长编写技术标文档。

【成功案例区域 — WIN_SIGNAL=POSITIVE】
当你看到标记为"成功经验"的案例时，学习其：
- 关键成功因素（key_win_factors）如何描述
- 突破性策略（win_breakthrough_tags）的呈现方式
- 评分维度的应对思路（scoring_dimension_tags）
- 如何将平凡的方案写出差异化优势

【避坑指南区域 — WIN_SIGNAL=NEGATIVE】
当你看到标记为"失败教训"的案例时，注意：
- 失败根因标签（loss_root_cause_tags）揭示的常见陷阱
- 避免在类似维度上重复同样的错误
- 如何在技术方案中明确规避已知的失分点

【评分维度聚焦】
每个案例都关联到特定评分维度（scoring_dimension_tags），如"食材溯源"、"冷链管理"。
生成内容时请优先覆盖本项目招标要求的评分维度。

【核心原则】
- 积极学习成功案例的写作策略和亮点提炼方式
- 主动规避失败案例中暴露的高频失分操作
- 输出的技术标内容必须同时满足：得分导向 + 风险规避 + 差异化表达"""


# ─── Rolling Summary Template (for long documents) ────────────────────────────

ROLLING_SUMMARY_TEMPLATE = """【历史资产摘要 — {chunk_index + 1}/{total_chunks}】
案例标签：{source_label}
胜负信号：{win_signal}
评分维度：{scoring_dimension_tags}
地区标签：{region_tags}
项目类型：{project_type_tags}

正文：
{content}

---"""


# ─── Context Assembly ─────────────────────────────────────────────────────────

def build_chunk_context(
    chunks: list[dict],
    max_positive_chars: int = 3000,
    max_negative_chars: int = 3000,
) -> str:
    """
    Assemble a dual-track context string from a list of chunk dicts.

    Separates positive (win_signal='positive') from negative (win_signal='negative')
    samples and renders each with the rolling summary template.

    Args:
        chunks: list of knowledge_chunks rows (as dicts with win_signal, etc.)
        max_positive_chars: character budget cap for positive section
        max_negative_chars: character budget cap for negative section

    Returns:
        Formatted multi-line string with WIN_TRACK and LOSS_TRACK sections.
    """
    positive_parts: list[str] = []
    negative_parts: list[str] = []

    for chunk in chunks:
        win_signal = chunk.get("win_signal") or "neutral"
        label = chunk.get("source_label") or chunk.get("chunk_type") or "未标注"
        dims = ", ".join(chunk.get("scoring_dimension_tags") or [])
        regions = ", ".join(chunk.get("region_tags") or [])
        ptypes = ", ".join(chunk.get("project_type_tags") or [])
        content = chunk.get("content", "")[:800]  # hard-truncate per chunk

        rendered = ROLLING_SUMMARY_TEMPLATE.format(
            chunk_index=chunk.get("chunk_index", 0),
            total_chunks=len(chunks),
            source_label=label,
            win_signal="成功经验" if win_signal == "positive" else "失败教训" if win_signal == "negative" else "一般参考",
            scoring_dimension_tags=dims or "通用",
            region_tags=regions or "通用",
            project_type_tags=ptypes or "通用",
            content=content,
        )

        if win_signal == "positive":
            positive_parts.append(rendered)
        elif win_signal == "negative":
            negative_parts.append(rendered)
        # neutral chunks are included in positive section by default

    def cap(text_parts: list[str], max_chars: int) -> str:
        """Join parts and truncate to max_chars."""
        joined = "\n".join(text_parts)
        if len(joined) <= max_chars:
            return joined
        return joined[:max_chars] + f"\n...（已截断，共 {len(joined)} 字符）"

    win_track = cap(positive_parts, max_positive_chars)
    loss_track = cap(negative_parts, max_negative_chars)

    # Build final dual-track block
    sections: list[str] = []

    if win_track:
        sections.append("【成功经验参考】\n" + win_track)
    if loss_track:
        sections.append("【失败教训参考】\n" + loss_track)

    if not sections:
        return "(当前无历史资产参考)"

    return "\n\n".join(sections)


def build_legacy_context(chunks: list[dict]) -> str:
    """
    Fallback context builder for chunks that do NOT carry win_signal metadata.
    Preserves the existing single-track context format used in active projects.
    """
    if not chunks:
        return "(当前无上下文参考)"

    parts = []
    for c in chunks:
        meta = c.get("metadata") or {}
        label = meta.get("source_label") or c.get("chunk_type", "文档片段")
        parts.append(f"[{label}]\n{c.get('text', '')[:500]}")

    return "\n\n".join(parts)
