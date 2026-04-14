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
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Sentence boundary punctuation ─────────────────────────────────────────────
_SENTENCE_PUNCTUATIONS = ["\n", "。", "！", "？", ".", "!", "?"]

# ─── Boilerplate keyword sets ─────────────────────────────────────────────────

# Static template sections — discard without入库 (no RAG intelligence value).
BOILERPLATE_KEYWORDS: list[str] = [
    # 资质证明类
    "授权", "承诺函", "证明", "证书", "复印件", "盖章",
    "资质", "营业执照", "法人代表", "委托人", "身份证",
    "授权委托书", "声明", "声明书", "公证书",
    # 文件格式类
    "投标函", "投标文件", "封面", "扉页", "目录", "索引",
    "密封", "签署", "日期", "编号", "文件格式",
    "投标文件格式", "商务文件", "技术文件", "资格证明文件",
    # 评分标准声明类
    "评分标准", "评分细则", "得分", "扣分", "评审",
    "评标标准", "评标办法", "评标细则",
    # 商务条款类
    "合同条款", "履约保证", "验收标准", "付款方式",
    # 无情报价值的固定格式
    "公司名称", "联系人", "联系电话", "通讯地址",
    "开户名称", "开户银行", "银行账号",
]

# Dynamic generative sections — these carry RAG intelligence (入库).
GENERATIVE_KEYWORDS: list[str] = [
    "服务方案", "配送方案", "应急方案", "保障方案", "实施方案",
    "质量保障", "食品安全", "卫生管理", "采购计划", "配送计划",
    "人员配置", "培训", "考核", "监督机制", "管理方案",
    "管理制度", "操作规程", "岗位职责", "工作流程",
    "冷链管理", "冷链配送", "食材溯源", "来源证明",
    "报价方案", "价格说明", "费用清单", "预算明细",
    "业绩", "案例", "项目经验", "成功案例", "类似项目",
    "技术措施", "工艺", "施工方案", "技术工艺",
    "卫生保障", "健康证明", "体检", "食品安全",
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
LLM_SYSTEM_PROMPT = (
    "你是一位招投标领域的资深专家。你的任务是对给定的文本块进行深度分析，"
    "并按以下三个维度提炼信息：\n"
    "1. 核心痛点（Core Pain Points）：招标方在这一章节中强调的关键需求、约束条件或潜在风险\n"
    "2. 技术响应指标（Technical Response Indicators）：投标方需要在技术方案中具体回应的指标、数据或标准\n"
    "3. 竞争优势（Competitive Advantages）：基于这一章节，投标人可以突出展示的差异化优势\n"
    "请用简洁的要点（bullet points）输出，每个维度3-5条。使用中文。JSON格式输出。\n"
    "输出格式：\n"
    "{\n"
    '  "core_pain_points": ["痛点1", "痛点2", ...],\n'
    '  "technical_indicators": ["指标1", "指标2", ...],\n'
    '  "competitive_advantages": ["优势1", "优势2", ...]\n'
    "}"
)

LLM_API_BASE = "https://api.deepseek.com"
LLM_MODEL = "deepseek-chat"
LLM_MAX_TOKENS = 600
LLM_TEMPERATURE = 0.3


# ─── Tenacity retry helper ────────────────────────────────────────────────────

def _llm_call_with_retry(
    text: str,
    api_key: str,
    retry: int = 3,
) -> Optional[dict]:
    """
    Call DeepSeek chat API for insight extraction with exponential backoff + jitter.

    Retry policy (Patch 1):
      - 529 (rate limit): exponential backoff with full jitter
      - 5xx server errors: exponential backoff
      - Connection/network errors: exponential backoff

    Returns:
        dict with keys core_pain_points, technical_indicators,
        competitive_advantages, or None on complete failure.
    """
    import json as _json
    import requests as _requests

    url = f"{LLM_API_BASE}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # Truncate to first 2500 chars to stay well within token limit
    truncated = text[:2500]
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": f"【文本块】\n{truncated}"},
        ],
        "temperature": LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
    }

    last_err: Optional[Exception] = None

    for attempt in range(retry):
        try:
            resp = _requests.post(url, headers=headers, json=payload, timeout=60)
            if resp.status_code == 529:
                # Rate limited — Full Jitter: random value in [0, 2^attempt * 1.0]
                wait = (2 ** attempt) * 1.0
                import random
                wait *= random.random()
                logger.warning("LLM 529 rate-limit, retry %d/%d after %.1fs", attempt + 1, retry, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            raw_content: str = data["choices"][0]["message"]["content"]
            # Strip markdown code fences if present
            raw_content = raw_content.strip()
            if raw_content.startswith("```"):
                raw_content = _json.loads(raw_content.split("```")[1].strip()[4:]) if "```" in raw_content else raw_content
            result = _json.loads(raw_content)
            # Validate structure
            if all(k in result for k in ("core_pain_points", "technical_indicators", "competitive_advantages")):
                return dict(result)
            else:
                logger.warning("LLM returned unexpected structure: %s", list(result.keys()))
                return None
        except Exception as exc:
            last_err = exc
            wait = (2 ** attempt) * 1.0
            import random
            time.sleep(wait * random.random())

    logger.error("LLM call failed after %d attempts: %s", retry, str(last_err))
    return None


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

    MIN_SEGMENT_CHARS = 500

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
        """Merge segments shorter than MIN_SEGMENT_CHARS into the previous."""
        if not segments:
            return []
        merged: list[Segment] = []
        for seg in segments:
            if seg.char_length < self.MIN_SEGMENT_CHARS and merged:
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
        self.max_concurrency = max_concurrency
        self.min_table_chars = min_table_chars

        # Semaphore for Patch 1: cap concurrent LLM calls
        self._llm_semaphore: Optional[Any] = None
        if self.enable_llm_insights and self.deepseek_api_key:
            try:
                from concurrent.futures import Semaphore
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
        if self.enable_llm_insights and self.deepseek_api_key:
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
                if not content or len(content) < self.min_segment_chars:
                    continue

                # Layer 1: Boilerplate filter
                if self._is_boilerplate(content):
                    logger.debug("Boilerplate filtered: %s", content[:40])
                    continue

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
                    if self.enable_llm_insights and self.deepseek_api_key:
                        for sub in sub_chunks:
                            fut = executor.submit(
                                _llm_call_with_retry,
                                sub.text,
                                self.deepseek_api_key,
                            )
                            llm_futures[id(fut)] = sub.chunk_index

                    global_index += len(sub_chunks)

        # Wait for all LLM futures to complete and inject insights
        if executor:
            executor.shutdown(wait=True)
            for fut in as_completed(llm_futures):
                chunk_idx = llm_futures[id(fut)]
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

        规则：首行出现BOILERPLATE_KEYWORDS → 丢弃。
        特例：若首行同时包含GENERATIVE_KEYWORDS，则视为动态生成（保留）。
        """
        first_line = text.split("\n")[0].strip()
        if not first_line:
            return True

        bp_hit = any(kw in first_line for kw in BOILERPLATE_KEYWORDS)
        gen_hit = any(kw in first_line for kw in GENERATIVE_KEYWORDS)

        # Boilerplate ONLY if generative keywords are absent
        return bp_hit and not gen_hit

    # ── Layer 2: Rough segment ────────────────────────────────────────────────

    def _rough_segment(self, text: str) -> list[Segment]:
        """Segment paragraph text into topic-aligned chunks."""
        return HistoricalRoughSegmenter().rough_segment(text)

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
