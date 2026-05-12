"""Shared types, constants, and data structures for the chunking pipeline.

This module contains:
- Navigation/boilerplate constants
- LLMCircuitBreakerError
- Segment and ChunkDict value objects
- HistoricalRoughSegmenter (coarse segmentation by headers)
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ─── Navigation / page-mark pattern filter ───────────────────────────────────

# Sentence boundary punctuation (shared by sliding window)
_SENTENCE_PUNCTUATIONS = ["\n", "。", "！", "？", ".", "!", "?"]

_NAVIGATION_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\d{1,2}\.\d{1,2}\.\d{1,2}\s+[\u4e00-\u9fa5【】]+[ \t]+\d{3,5}$"),
    re.compile(r"^\d{1,2}\.\d{1,2}\.\d{1,2}[ \t　]+[\u4e00-\u9fa5【】]+[ \t　]+\d{3,5}$"),
    re.compile(r"^[\u4e00-\u9fa5]+[ \t　]+\d{4,}$"),
    re.compile(r"^第[一二三四五六七八九十百\d]+章[ \t　]+[\u4e00-\u9fa5]+[ \t　]+\d+$"),
]

def _is_navigation_marker(text: str) -> bool:
    """Check if text is a pure navigation/page-mark pattern (header/footer/page#)."""
    stripped = text.strip()
    if not stripped:
        return False
    if len(stripped) > 100:
        return False
    for pattern in _NAVIGATION_PATTERNS:
        if pattern.match(stripped):
            return True
    return False


# ─── Boilerplate keyword sets ──────────────────────────────────────────────────

BOILERPLATE_KEYWORDS: list[str] = [
    "盖章处", "（公章）", "（法人章）",
    "投标函", "响应函", "澄清函",
    "封面", "扉页", "目录", "索引", "附件",
    "密封", "正本", "副本",
    "此页无正文", "（此页空白）",
    "得分汇总", "最终得分",
    "法定代表人", "被授权人", "身份证复印件", "营业执照复印件",
    "（复印件）", "（副本）", "（盖章）",
]

GENERATIVE_KEYWORDS: list[str] = [
    "服务方案", "配送方案", "应急方案", "保障方案", "实施方案",
    "服务要求", "技术要求", "服务承诺",
    "质量保障", "食品安全", "卫生管理", "卫生保障", "安全保障",
    "质量管理体系", "食品安全管理体系",
    "采购计划", "采购流程", "采购需求", "采购管理",
    "配送方案", "配送计划", "配送服务", "配送流程", "配送管理",
    "冷链配送", "冷链管理", "冷链物流",
    "管理方案", "管理制度", "管理措施", "管理体系",
    "运营方案", "运营管理", "日常管理",
    "人员配置", "人员安排", "培训计划", "培训方案", "考核机制",
    "岗位职责", "工作流程", "操作规程",
    "食材溯源", "来源证明", "产地证明", "检疫证明", "合格证明",
    "原材料管理", "食品留样",
    "报价方案", "价格说明", "费用清单", "预算明细", "成本分析",
    "报价说明", "价格策略",
    "业绩", "案例", "项目经验", "成功案例", "类似项目", "既往业绩",
    "企业业绩", "典型案例",
    "技术措施", "技术方案", "技术工艺", "施工方案", "工艺流程",
    "技术响应", "技术路线",
    "监督机制", "应急预案", "应急措施", "应急保障", "风险防控",
    "健康证明", "体检", "资质证书", "体系认证",
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


# ─── Exception ──────────────────────────────────────────────────────────────

class LLMCircuitBreakerError(Exception):
    """Raised when LLM fails 3 times consecutively — signals main thread to exit."""
    pass


# ─── Value objects ───────────────────────────────────────────────────────────

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
    """

    __slots__ = ("text", "chunk_index", "char_length", "metadata")

    def __init__(self, text: str, chunk_index: int, metadata: dict[str, Any]) -> None:
        self.text: str = text
        self.chunk_index: int = chunk_index
        self.char_length: int = len(text)
        self.metadata: dict[str, Any] = metadata

    def to_dict(self) -> dict[str, Any]:
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

    MIN_SEGMENT_CHARS = 20

    def __init__(self, min_segment_chars: int = 500):
        self.min_segment_chars = min_segment_chars

    def rough_segment(self, text: str) -> list[Segment]:
        """Split document text into topic-aligned segments by header detection."""
        if not text or text.isspace():
            return []

        lines = text.split("\n")
        segments: list[Segment] = []
        current_body_lines: list[str] = []
        current_title = ""
        current_tags: set[str] = set()

        def _flush(title: str, body_lines: list[str], tags: set[str]) -> None:
            body = "\n".join(body_lines).strip()
            if not body and title.strip():
                body = title.strip()
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
        """Return (is_header, header_type, header_name) for a line.

        Header detection rules:
        - chapter: 第X章
        - section: 一、 二、
        - subsection: （一）
        - numbered: 1. 1.1 (BUT NOT: 9.4 without trailing content word)
        - keyword: 服务方案, 评分标准, etc.

        Single header-like line with trailing page number (e.g. "9.4 参加采购活动... 61")
        is NOT treated as a header — it is treated as body text.
        """
        for header_type, pattern in self.HEADER_PATTERNS:
            if pattern.match(line):
                if header_type == "numbered":
                    stripped = line.strip()
                    if re.match(r"^\d+\.\d+\s+[\d\uff0e]+$", stripped):
                        return False, "", ""
                    if re.search(r"\s+\d{1,4}\s*$", stripped) and len(stripped.split()) <= 3:
                        return False, "", ""
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
        if not segments:
            return []
        merged = [segments[0]]
        for seg in segments[1:]:
            if seg.char_length < self.min_segment_chars and merged:
                last = merged[-1]
                last.body += "\n" + seg.body
                last.char_length = len(last.body)
                last.dimension_tags = list(set(last.dimension_tags + seg.dimension_tags))
            else:
                merged.append(seg)
        return merged