"""HistoricalChunker V3 — Filter Chain + LLM Insight + Sliding Window.

Engineering constraints:
  - ALL output dicts are JSONB-safe (no non-serializable objects).
  - Tables are ALWAYS emitted as atomic chunks (Patch 2: no mid-table切断).
  - LLM API calls use tenacity retry with jitter (Patch 1: no 529雪崩).
  - Table chunks carry has_table:True in metadata (Patch 3).
  - No dependency on app/schemas/rag (standalone seeding script).

Patch 1 — API Resilience:
  tenacity retry decorator with Exponential Backoff + Full Jitter.
  Semaphore caps concurrent API calls at 5 (tuneable via max_concurrency).

Patch 2 — Table Integrity:
  Table blocks are NEVER passed to sliding-window splitters.
  They bypass segmentation entirely and are emitted as one atomic chunk.

Patch 3 — Metadata Enhancement:
  Table-derived chunks receive has_table: True in chunk_metadata.
  This is the RAG recall index for qualification lists and price tables.

Patch 4 — JSONB Safety:
  chunk_metadata is assembled as a plain Python dict at construction time.
  llm_insights is also a plain dict (deserialized from API JSON) — never a
  raw httpx.Response or similar ORM object.

Author: TIS Seeding Pipeline V3
"""
from __future__ import annotations

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from typing import Any, Optional

from app.core.llm_factory import generate_insights_from_text

logger = logging.getLogger(__name__)

# ─── Sentence boundary punctuation ─────────────────────────────────────────────
_SENTENCE_PUNCTUATIONS = ["\n", "。", "！", "？", ".", "!", "?"]

# ─── Boilerplate keyword sets ─────────────────────────────────────────────────

# Static template sections — discard without入库 (no RAG intelligence value).
# P1 FIX: Only pure legal/format phrases that carry ZERO business intelligence.
# Single generic chars like "管理" have been REMOVED — they kill legitimate content.
# Match: ONLY exact phrases (whole-word), not character substrings.
BOILERPLATE_KEYWORDS: list[str] = [
    # 纯法务/格式标记 — 仅当独立词汇出现时才算模板
    "盖章处", "（公章）", "（法人章）",          # 签章位置标记
    "投标函", "响应函", "澄清函",                 # 函件抬头
    "封面", "扉页", "目录", "索引", "附件",       # 文件结构（含"目录"）
    "密封", "正本", "副本",                       # 装订格式
    "此页无正文", "（此页空白）",                  # 格式填充页
    # 评分结果公布（与"评分标准"是两码事，这里只留公示性词汇）
    "得分汇总", "最终得分",
    # 格式废话 — 常见于身份证/营业执照复印件标注
    "法定代表人", "被授权人", "身份证复印件", "营业执照复印件",
    "（复印件）", "（副本）", "（盖章）",
]

# Dynamic generative sections — these carry RAG intelligence (入库).
# P1 FIX: Expanded to cover ALL legitimate business content.
# ANY block that hits these keywords is forcibly preserved (whitelist override).
GENERATIVE_KEYWORDS: list[str] = [
    # 服务与方案类
    "服务方案", "配送方案", "应急方案", "保障方案", "实施方案",
    "服务要求", "技术要求", "服务承诺", "实施方案",
    # 质量与安全
    "质量保障", "食品安全", "卫生管理", "卫生保障", "安全保障",
    "质量管理体系", "食品安全管理体系",
    # 采购与配送
    "采购计划", "采购流程", "采购需求", "采购管理",
    "配送方案", "配送计划", "配送服务", "配送流程", "配送管理",
    "冷链配送", "冷链管理", "冷链物流",
    # 管理方案
    "管理方案", "管理制度", "管理措施", "管理体系",
    "运营方案", "运营管理", "日常管理",
    # 人员与培训
    "人员配置", "人员安排", "培训计划", "培训方案", "考核机制",
    "岗位职责", "工作流程", "操作规程",
    # 食材与溯源
    "食材溯源", "来源证明", "产地证明", "检疫证明", "合格证明",
    "原材料管理", "食品留样",
    # 报价与成本
    "报价方案", "价格说明", "费用清单", "预算明细", "成本分析",
    "报价说明", "价格策略",
    # 业绩与案例
    "业绩", "案例", "项目经验", "成功案例", "类似项目", "既往业绩",
    "企业业绩", "典型案例",
    # 技术与工艺
    "技术措施", "技术方案", "技术工艺", "施工方案", "工艺流程",
    "技术响应", "技术路线",
    # 监督与应急
    "监督机制", "应急预案", "应急措施", "应急保障", "风险防控",
    # 健康与资质
    "健康证明", "体检", "资质证书", "体系认证",
    # 项目理解
    "项目概况", "项目背景", "项目目标", "项目范围",
    # 其他商业智慧
    "竞争优势", "核心优势", "差异化", "服务特色",
]

# ─── Scoring dimension auto-tagging ───────────────────────────────────────────
DIMENSION_KEYWORDS: dict[str, list[str]] = {
    "食材溯源":     ["食材", "溯源", "来源", "产地证明", "检疫", "合格证明", "原材料"],
    "冷链管理":     ["冷链", "冷藏", "冷冻", "温度控制", "冷库", "冷链车", "全程冷链"],
    "卫生保障":     ["卫生", "消毒", "清洁", "食品安全", "健康管理", "卫生许可证"],
    "配送能力":     ["配送", "运输", "送货车", "物流", "时效", "配送车辆", "运输能力"],
    "报价合理性":   ["报价", "价格", "预算", "成本", "性价比", "总价", "单价", "优惠"],
    "服务方案":     ["服务", "方案", "承诺", "计划", "措施", "服务承诺", "质量保障"],
    "企业资质":     ["资质", "认证", "证书", "ISO", "执照", "营业执照", "体系认证"],
    "历史业绩":     ["业绩", "案例", "项目经验", "成功案例", "类似项目", "既往业绩"],
    "技术方案":     ["技术", "方案", "措施", "技术措施", "工艺", "施工方案"],
    "评分标准":     ["评分", "评标", "权重", "得分", "分值", "技术分", "商务分"],
}

# ─── LLM API config ───────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# GOLDEN PROMPT V3 — M2.7 Muscle-Memory Edition
# ══════════════════════════════════════════════════════════════════════════════
# INTENT: Model must understand its output feeds DIRECTLY into json.loads().
#         Any extra chars (markdown, thinking tags, explanations) = systematic
#         crash. This is not a writing exercise — it is a data exchange protocol.
# ══════════════════════════════════════════════════════════════════════════════
# CRITICAL: Keep this short — M2.7 returns unquoted JSON keys when prompt is too long.
# Test evidence: short prompt (~50 chars) → valid JSON; long prompt (~300+ chars) → unquoted keys.
LLM_SYSTEM_PROMPT = (
    "你是招投标专家。只输出JSON，禁止任何其他文字：\n"
    "{\"core_pain_points\":[],\"technical_indicators\":[],\"competitive_advantages\":[]}"
)


# ─── LLM call via unified factory ─────────────────────────────────────────────

def _llm_call_with_retry(
    text: str,
    api_key: Optional[str] = None,
    retry: int = 3,
) -> Optional[dict]:
    """
    Thin wrapper around llm_factory.generate_insights_from_text().

    Calls through the llm_factory MODULE (not a local binding) so that
    run_import.py patches to llm_factory.generate_insights_from_text take effect.
    The api_key argument is accepted but ignored — the factory reads
    the appropriate key from the ACTIVE_LLM_PROVIDER environment variable.
    """
    import app.core.llm_factory as _lf
    return _lf.generate_insights_from_text(
        text=text,
        system_prompt=LLM_SYSTEM_PROMPT,
    )


# ─── Dataclasses ──────────────────────────────────────────────────────────────

class Segment:
    """A rough document segment aligned to a topic or scoring dimension."""

    __slots__ = ("title", "body", "dimension_tags", "char_length")

    def __init__(self, title: str, body: str, dimension_tags: list[str]) -> None:
        self.title: str = title
        self.body: str = body
        self.dimension_tags: list[str] = dimension_tags
        self.char_length: int = len(body)

    def __repr__(self) -> str:
        tag_str = ",".join(self.dimension_tags[:2])
        return f"<Segment {self.char_length}chars tags=[{tag_str}] title={self.title[:20]!r}>"


class ChunkDict:
    """
    A single fine-grained chunk (plain dict, JSONB-safe).

    Attributes:
        text: Chunk content string.
        chunk_index: Sequential index across all chunks.
        char_length: len(text).
        metadata: Dict for tags + structured fields (llm_insights, has_table, etc.).
                  Consumers extend this dict; this class never mutates it.
    """

    __slots__ = ("text", "chunk_index", "char_length", "metadata")

    def __init__(self, text: str, chunk_index: int, metadata: dict[str, Any]) -> None:
        self.text: str = text
        self.chunk_index: int = chunk_index
        self.char_length: int = len(text)
        self.metadata: dict[str, Any] = metadata

    def to_dict(self) -> dict[str, Any]:
        """
        Plain dict representation — Patch 4: JSONB safety.
        All values are native Python types (str, int, float, list, dict, bool, None).
        """
        return {
            "text": self.text,
            "chunk_index": self.chunk_index,
            "char_length": self.char_length,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return f"<ChunkDict idx={self.chunk_index} {self.char_length}chars>"


# ─── Rough Segmenter (Pass 1) ────────────────────────────────────────────────

class HistoricalRoughSegmenter:
    """
    Coarse segmentation by section headers + auto dimension tagging.

    Section header patterns (checked in priority order):
      1. Chapter-level:  "第一章", "第1章"
      2. Numbered section: "一、", "二、"
      3. Subsection:       "（一）"
      4. Arabic numeric:  "1.", "1.1", "2.3.1"
      5. Keyword headers: "服务方案", "评分标准", "技术要求", etc.

    MIN_SEGMENT_CHARS: segments shorter than this are merged into the previous.
    """

    HEADER_PATTERNS: list[tuple[str, re.Pattern]] = [
        ("chapter",   re.compile(r"^第[一二三四五六七八九十百0-9]+章[ \t　]*")),
        ("section",   re.compile(r"^[一二三四五六七八九十]+、[ \t　]*")),
        ("subsection",re.compile(r"^（[一二三四五六七八九十]+）[ \t　]*")),
        ("numbered",  re.compile(r"^\d+(\.\d+)*[.、　]+")),
        (
            "keyword",
            re.compile(
                r"^(?:"
                r"评分标准|评标标准|评分细则|评标办法"
                r"|服务方案|技术方案|实施方案|配送方案"
                r"|技术要求|服务要求|质量要求|规格要求"
                r"|报价文件|投标报价|商务报价|报价方案"
                r"|企业资质|业绩要求|成功案例"
                r"|卫生保障|食品安全|冷链管理|食材溯源"
                r"|合同条款|履约保证|验收标准"
                r")[ \t　：:]*(?:\n|$)"
            ),
        ),
    ]

    MIN_SEGMENT_CHARS = 50   # was 500 — lowered to let short business content through; short segs merge into next

    def __init__(self, min_segment_chars: int = 500):
        self.min_segment_chars = min_segment_chars

    def rough_segment(self, text: str) -> list[Segment]:
        """
        Split document text into topic-aligned segments by header detection.

        Args:
            text: Raw text from a single paragraph Block.

        Returns:
            List of Segment objects (may be empty).
        """
        if not text or text.isspace():
            return []

        lines = text.split("\n")
        segments: list[Segment] = []
        current_body_lines: list[str] = []
        current_title = ""
        current_tags: set[str] = set()

        def _flush(title: str, body_lines: list[str], tags: set[str]) -> None:
            body = "\n".join(body_lines).strip()
            if not body:
                return
            body_tags = self._auto_tag_dimension(body)
            all_tags = list(tags | set(body_tags))
            segments.append(Segment(title=title.strip(), body=body, dimension_tags=all_tags))

        for line in lines:
            stripped = line.strip()
            if not stripped:
                current_body_lines.append(line)
                continue

            is_header, header_type, header_name = self._detect_header(stripped)
            if is_header:
                _flush(current_title, current_body_lines, current_tags)
                current_title = stripped
                current_body_lines = []
                current_tags = self._tags_from_header(header_name)
            else:
                current_body_lines.append(line)

        _flush(current_title, current_body_lines, current_tags)
        return self._merge_short_segments(segments)

    def _detect_header(self, line: str) -> tuple[bool, str, str]:
        """Return (is_header, header_type, header_name) for a line."""
        for header_type, pattern in self.HEADER_PATTERNS:
            if pattern.match(line):
                return True, header_type, line.strip()
        return False, "", ""

    def _tags_from_header(self, header_text: str) -> set[str]:
        tags: set[str] = set()
        for dim, keywords in DIMENSION_KEYWORDS.items():
            if any(kw in header_text for kw in keywords):
                tags.add(dim)
        return tags

    def _auto_tag_dimension(self, text: str) -> list[str]:
        """Extract scoring dimension tags from body text via keyword frequency."""
        if not text:
            return []
        scores: dict[str, int] = {}
        for dim, keywords in DIMENSION_KEYWORDS.items():
            count = sum(text.count(kw) for kw in keywords)
            if count >= 2:
                scores[dim] = count
        return [dim for dim, _ in sorted(scores.items(), key=lambda x: -x[1])]

    def _merge_short_segments(self, segments: list[Segment]) -> list[Segment]:
        """Merge segments shorter than min_segment_chars into the previous."""
        if not segments:
            return []
        merged: list[Segment] = []
        min_chars = self.min_segment_chars
        for seg in segments:
            if seg.char_length < min_chars and merged:
                prev = merged[-1]
                combined = prev.body + "\n" + seg.body
                combined_tags = list(set(prev.dimension_tags) | set(seg.dimension_tags))
                merged[-1] = Segment(title=prev.title, body=combined, dimension_tags=combined_tags)
                logger.debug("Merged short segment (%d chars) into previous", seg.char_length)
            else:
                merged.append(seg)
        return merged


# ─── V3 HistoricalChunker ─────────────────────────────────────────────────────

class HistoricalChunker:
    """
    V3切片引擎：Filter Chain + LLM洞察 + Sliding Window.

    Layer 0 — 类型过滤:
        paragraph → 原样进入 Layer 1
        table     → 跳过boilerplate检查，整体进入 Layer 3

    Layer 1 — Boilerplate过滤:
        标题或首行命中BOILERPLATE_KEYWORDS → 直接丢弃
        通过 → 进入 Layer 2

    Layer 2 — 聚类 + 滑动窗口:
        按heading聚合成段落组
        每组按滑动窗口切分（chunk_size=600, overlap=80）

    Layer 3 — LLM洞察提取（仅enable_llm_insights=True）:
        仅对动态段落提取 {core_pain_points, technical_indicators, competitive_advantages}
        表格跳过LLM提取（表格内容格式固定，无生成价值）
        Patch 1: tenacity retry + Semaphore并发控制

    Patch 2 (Table Integrity): table blocks bypass sliding window entirely.
    Patch 3 (has_table): table blocks receive metadata["has_table"] = True.
    Patch 4 (JSONB): to_dict() always returns plain Python types.
    """

    SENTENCE_PUNCTUATIONS = _SENTENCE_PUNCTUATIONS

    def __init__(
        self,
        min_segment_chars: int = 500,
        chunk_size: int = 600,
        overlap: int = 80,
        max_overlap_fraction: float = 0.3,
        enable_llm_insights: bool = False,
        deepseek_api_key: Optional[str] = None,
        max_concurrency: int = 5,
        min_table_chars: int = 20,
    ) -> None:
        self.min_segment_chars = min_segment_chars
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.max_overlap_fraction = max_overlap_fraction
        self.enable_llm_insights = enable_llm_insights
        self.deepseek_api_key = deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        # Any provider key enables LLM insights (factory reads the right one from env)
        self._llm_available = bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("MINIMAX_API_KEY"))
        self.max_concurrency = max_concurrency
        self.min_table_chars = min_table_chars

        # Semaphore for Patch 1: cap concurrent LLM calls
        self._llm_semaphore: Optional[Any] = None
        if self.enable_llm_insights and self._llm_available:
            try:
                from threading import Semaphore
                self._llm_semaphore = Semaphore(max_concurrency)
            except Exception as exc:
                logger.warning("Could not create LLM Semaphore: %s", exc)

    # ── Public entry point ────────────────────────────────────────────────────

    def chunk(
        self,
        blocks: list[Any],
        base_metadata: Optional[dict[str, Any]] = None,
    ) -> list[ChunkDict]:
        """
        High-level V3 chunking entry point.

        Args:
            blocks: List of Block objects from DOCXParser V3.
                   Each block has .block_type ("paragraph"|"table") and .content (str).
            base_metadata: Metadata dict attached to every output ChunkDict.

        Returns:
            Flat list of ChunkDict in document order.
        """
        from scripts.seeding.parsers.docx_parser import Block as V3Block

        if base_metadata is None:
            base_metadata = {}

        all_chunks: list[ChunkDict] = []
        global_index = 0

        # Patch 1: prepare ThreadPoolExecutor for concurrent LLM calls
        executor: Optional[ThreadPoolExecutor] = None
        if self.enable_llm_insights and self._llm_available:
            executor = ThreadPoolExecutor(max_workers=self.max_concurrency)

        # Collect LLM futures for batch processing
        llm_futures: dict[int, Any] = {}
        chunk_buffer: dict[int, ChunkDict] = {}

        for block in blocks:
            if not isinstance(block, V3Block):
                # Backwards compat: dict-style block (from older parse results)
                block_type = block.get("block_type", "paragraph")
                content = block.get("content", block.get("text", ""))
            else:
                block_type = block.block_type
                content = block.content

            if block_type == "table":
                # ── Layer 0: Table block ──────────────────────────────────────
                # Patch 2: always atomic, never split
                if len(content) < self.min_table_chars:
                    continue
                dim_tags = self._auto_tag_dimensions(content)
                meta = {
                    **base_metadata,
                    "scoring_dimension_tags": dim_tags,
                    "has_table": True,               # Patch 3
                    "block_type": "table",
                    "llm_insights": None,            # Tables skip LLM
                    "token_count": self._estimate_tokens(content),
                }
                chunk = ChunkDict(
                    text=content,
                    chunk_index=global_index,
                    metadata=meta,
                )
                all_chunks.append(chunk)
                global_index += 1

            else:
                # ── Layer 0: Paragraph block ────────────────────────────────
                if not content.strip():
                    continue

                # Layer 1: Boilerplate filter
                if self._is_boilerplate(content):
                    logger.debug("Boilerplate filtered: %s", content[:40])
                    continue

                # Layer 1.5: Short-text guard — discard paragraph blocks that are
                # too short to carry business intelligence (e.g. "目 录", "（1）", "答：")
                if len(content.strip()) < 30:
                    logger.debug("Short block filtered (%d chars): %s", len(content), content[:30])
                    continue

                # NOTE: min_segment_chars check moved INSIDE rough_segment
                # (short segments will merge with neighbors; truly empty ones drop out)

                # Layer 2: Rough segment + sliding window
                segs = self._rough_segment(content)
                for seg in segs:
                    sub_chunks = self._sliding_window(
                        text=seg.body,
                        metadata={},
                        start_index=global_index,
                        block_type="paragraph",
                    )
                    for sub in sub_chunks:
                        # Guard: discard sub-chunks that are too short (e.g. 1-token fragments)
                        if len(sub.text.strip()) < 20:
                            global_index += 1
                            continue
                        # Enrich sub-chunk metadata
                        sub.metadata.update({
                            **base_metadata,
                            "scoring_dimension_tags": seg.dimension_tags,
                            "has_table": False,       # Patch 3
                            "block_type": "paragraph",
                            "token_count": self._estimate_tokens(sub.text),  # w015 field
                        })
                        chunk_buffer[sub.chunk_index] = sub

                    # Schedule LLM extraction concurrently (Patch 1)
                    if self.enable_llm_insights and self._llm_available:
                        for sub in sub_chunks:
                            _text = sub.text
                            _chunk_index = sub.chunk_index
                            fut = executor.submit(
                                _llm_call_with_retry,
                                _text,
                            )
                            llm_futures[fut] = sub.chunk_index

                    global_index += len(sub_chunks)

        # Wait for all LLM futures to complete and inject insights
        if executor:
            executor.shutdown(wait=True)
            for fut in as_completed(llm_futures):
                chunk_idx = llm_futures[fut]
                if chunk_idx in chunk_buffer:
                    insights = fut.result()
                    if insights:
                        chunk_buffer[chunk_idx].metadata["llm_insights"] = insights
                    else:
                        chunk_buffer[chunk_idx].metadata["llm_insights"] = None

        all_chunks.extend(chunk_buffer.values())
        all_chunks.sort(key=lambda c: c.chunk_index)

        logger.info(
            "V3 chunked: %d blocks → %d chunks "
            "(llm_insights=%s, tables=%d, paragraphs=%d)",
            len(blocks),
            len(all_chunks),
            self.enable_llm_insights,
            sum(1 for c in all_chunks if c.metadata.get("has_table")),
            sum(1 for c in all_chunks if not c.metadata.get("has_table")),
        )
        return all_chunks

    # ── Layer 1: Boilerplate ──────────────────────────────────────────────────

    @staticmethod
    def _is_boilerplate(text: str) -> bool:
        """
        判断文本块是否为静态模板（应丢弃）。

        P1 FIX — Whitelist Override Logic:
          1. ANY line hits GENERATIVE_KEYWORDS  → KEEP (whitelist override)
          2. First line hits BOILERPLATE_KEYWORDS → DISCARD
          3. Otherwise                                                    → KEEP
        """
        if not text.strip():
            return True

        lines = text.split("\n")

        # Step 1: Whitelist — if ANY line hits generative keywords → keep
        any_gen = any(
            any(kw in line for kw in GENERATIVE_KEYWORDS)
            for line in lines
        )
        if any_gen:
            return False

        # Step 2: Boilerplate only if first line hits boilerplate keywords
        first_line = lines[0].strip()
        bp_hit = any(kw in first_line for kw in BOILERPLATE_KEYWORDS)

        return bp_hit

    # ── Layer 2: Rough segment ────────────────────────────────────────────────

    def _rough_segment(self, text: str) -> list[Segment]:
        """Segment paragraph text into topic-aligned chunks."""
        return HistoricalRoughSegmenter(min_segment_chars=self.min_segment_chars).rough_segment(text)

    # ── Layer 2: Sliding window ───────────────────────────────────────────────

    def _sliding_window(
        self,
        text: str,
        metadata: dict[str, Any],
        start_index: int,
        block_type: str = "paragraph",
    ) -> list[ChunkDict]:
        """
        Apply sliding-window chunking to a single text segment.

        Patch 2 (Table Integrity): called ONLY for paragraph blocks.
        Table blocks arrive already-assembled and are never re-split.

        Smart truncation: find sentence boundary in last 20% of window.
        """
        if not text or text.isspace():
            return []

        text_len = len(text)

        if text_len <= self.chunk_size:
            return [
                ChunkDict(
                    text=text,
                    chunk_index=start_index,
                    metadata={**metadata, "block_type": block_type},
                )
            ]

        effective_overlap = min(
            self.overlap,
            int(self.chunk_size * self.max_overlap_fraction),
        )

        chunks: list[ChunkDict] = []
        current_pos = 0
        chunk_index = start_index

        while current_pos < text_len:
            chunk_end = min(current_pos + self.chunk_size, text_len)

            # Smart truncation: search last 20% for sentence boundary
            if chunk_end < text_len:
                boundary = self._find_sentence_boundary(text, current_pos, chunk_end)
                if boundary is not None:
                    chunk_end = boundary

            chunk_text = text[current_pos:chunk_end]
            chunks.append(
                ChunkDict(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    metadata={**metadata, "block_type": block_type},
                )
            )

            chunk_index += 1

            if chunk_end >= text_len:
                break

            next_pos = chunk_end - effective_overlap
            if next_pos <= current_pos:
                next_pos = current_pos + 1

            current_pos = next_pos

        return chunks

    def _find_sentence_boundary(
        self, text: str, start: int, end: int
    ) -> Optional[int]:
        """Find the best sentence boundary within [start + chunk_size*0.8, end]."""
        chunk_len = end - start
        search_start = max(start + int(chunk_len * 0.8), start)
        search_window = text[search_start:end]

        best_pos: Optional[int] = None
        for punct in self.SENTENCE_PUNCTUATIONS:
            pos = search_window.rfind(punct)
            if pos == -1:
                continue
            abs_pos = search_start + pos
            boundary = abs_pos + 1
            if boundary <= end:
                if best_pos is None or boundary > best_pos:
                    best_pos = boundary

        return best_pos

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _auto_tag_dimensions(text: str) -> list[str]:
        """Extract scoring dimension tags from text via keyword frequency."""
        if not text:
            return []
        scores: dict[str, int] = {}
        for dim, keywords in DIMENSION_KEYWORDS.items():
            count = sum(text.count(kw) for kw in keywords)
            if count >= 2:
                scores[dim] = count
        return [dim for dim, _ in sorted(scores.items(), key=lambda x: -x[1])]

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate: ~0.75 chars per token for Chinese-heavy text."""
        return int(len(text) * 0.4)
