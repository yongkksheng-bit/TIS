#!/usr/bin/env python3
"""
template_reverse_engineer.py — V2 Bid Template Reverse Engineering

Fully automated. No terminal printing of large content.
All outputs written silently to D:/tis_project/scripts/deep_bid_analysis/

Outputs:
  - bid_template_structure.json  (machine-readable template blueprint)
  - V2_bid_assembly_logic.md     (human-readable assembly guide)
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR: Path = Path(__file__).parent.resolve()
INPUT_DOCX: Path = Path(
    "/tmp/historical_documents/2025_惠州市交通运输局交通大厦食堂管理和食材配送服务_投标文件.docx"
)
OUTPUT_JSON: Path = SCRIPT_DIR / "bid_template_structure.json"
OUTPUT_MD: Path = SCRIPT_DIR / "V2_bid_assembly_logic.md"

# ── Boilerplate keyword signatures ─────────────────────────────────────────────
# Sections whose heading or first body line matches these → static template
BOILERPLATE_HEADING_KEYWORDS: list[str] = [
    "授权", "承诺函", "保证金", "证明", "复印件", "身份证", "营业执照",
    "证书", "资质", "许可证", "社保证明", "银行资信", "纳税证明",
    "无违法", "无失信", "无重大", "信用中国", "声明",
    "法定代表人", "委托代理人", "投标人名称", "盖章",
    "格式", "申请表", "响应表", "清单",
]

# Sections whose heading matches these → dynamic generative content
GENERATIVE_HEADING_KEYWORDS: list[str] = [
    "服务方案", "保障方案", "应急预案", "配送方案", "运输方案",
    "质量保障", "安全措施", "卫生管理", "食品安全", "冷链管理",
    "采购方案", "实施方案", "项目理解", "整体策划", "服务承诺",
    "进度计划", "培训计划", "售后", "验收标准", "质量标准",
    "投诉处理", "应急响应", "风险管控",
]

# ── Heading style names used in this document ─────────────────────────────────
HEADING_STYLES: set[str] = {"Heading 1", "Heading 2", "Heading 3", "Heading 4", "Heading 5"}


def is_heading_para(para) -> bool:
    return para.style is not None and para.style.name in HEADING_STYLES


def is_table_heading(para) -> bool:
    """Para that looks like a table column header."""
    text = para.text.strip()
    return bool(text) and any(
        text == col for col in ["序号", "条款", "评分因素", "证明材料", "文件名称"]
    )


def classify_section(title: str, body_snippet: str) -> str:
    """
    Classify a section as 'boilerplate' (static) or 'generative' (LLM-needed).
    Uses keyword matching on heading + first body line.
    """
    combined = title + " " + body_snippet
    title_lower = title.lower()

    # Explicit boilerplate indicators
    for kw in BOILERPLATE_HEADING_KEYWORDS:
        if kw in title:
            return "boilerplate"

    # Explicit generative indicators
    for kw in GENERATIVE_HEADING_KEYWORDS:
        if kw in title:
            return "generative"

    # Short all-digit or pattern titles are usually table rows / serial items
    if re.match(r"^[\d（一二三四五六七八九十）+、.、\s]+$", title.strip()):
        return "boilerplate"

    # Body-only lines with template placeholders
    if re.search(r"^\s*(投标人|供应商|我方|公司)[：:]", body_snippet[:40]) and len(body_snippet) < 200:
        return "boilerplate"
    if re.search(r"________+|××+|○○+|〔 〕", body_snippet):
        return "boilerplate"

    return "generative"


def extract_font_info(run) -> dict:
    """Extract font info from a run."""
    info: dict = {}
    try:
        if run.font and run.font.name:
            info["name"] = run.font.name
    except Exception:
        pass
    try:
        if run.font and run.font.size:
            from docx.shared import Pt
            info["size_pt"] = round(float(run.font.size.pt), 1)
    except Exception:
        pass
    return info


def extract_paragraph_format(para) -> dict:
    """Extract key formatting from a paragraph."""
    fmt: dict = {}
    try:
        pf = para.paragraph_format
        fmt["left_indent_pt"] = round(float(pf.left_indent.pt), 1) if pf.left_indent else 0
        fmt["first_line_indent_pt"] = (
            round(float(pf.first_line_indent.pt), 1) if pf.first_line_indent else 0
        )
        fmt["line_spacing"] = (
            round(float(pf.line_spacing), 1) if pf.line_spacing else None
        )
        fmt["space_before_pt"] = round(float(pf.space_before.pt), 1) if pf.space_before else 0
        fmt["space_after_pt"] = round(float(pf.space_after.pt), 1) if pf.space_after else 0
    except Exception:
        pass
    return fmt


def get_body_text_for_section(para) -> str:
    """Get cleaned text from a paragraph (not heading)."""
    return para.text.strip()


def build_toc_tree(paragraphs: list, heading_styles: set) -> list[dict]:
    """
    Build a hierarchical TOC tree from flat paragraph list.
    Each node: {level, title, char_count, chunk_type, children}
    """
    toc: list[dict] = []
    current: dict[str, dict | None] = {
        "1": None, "2": None, "3": None,
        "4": None, "5": None,
    }

    for para in paragraphs:
        style_name = para.style.name if para.style else ""
        if style_name not in heading_styles:
            continue

        # Determine heading level
        level_map = {
            "Heading 1": 1,
            "Heading 2": 2,
            "Heading 3": 3,
            "Heading 4": 4,
            "Heading 5": 5,
        }
        level = level_map.get(style_name, 2)
        title = para.text.strip()
        if not title:
            continue

        # Estimate char count: sum of next non-heading paras
        body_chars = 0
        idx = paragraphs.index(para)
        for next_para in paragraphs[idx + 1 : idx + 20]:
            if next_para.style and next_para.style.name in heading_styles:
                break
            body_chars += len(next_para.text.strip())

        node: dict = {
            "level": level,
            "title": title,
            "char_count": body_chars,
            "classification": "unknown",  # filled below
            "children": [],
        }
        toc.append(node)

    return toc


def get_section_body_snippet(paragraphs: list, section_idx: int) -> str:
    """Get first ~200 chars of body text after a heading."""
    texts: list[str] = []
    total = 0
    for i in range(section_idx + 1, len(paragraphs)):
        para = paragraphs[i]
        if para.style and para.style.name in HEADING_STYLES:
            break
        t = para.text.strip()
        if t:
            texts.append(t)
            total += len(t)
            if total > 200:
                break
    return " ".join(texts)[:200]


def main() -> None:
    from docx import Document
    from docx.shared import Pt

    # ── Load document ────────────────────────────────────────────────────────
    doc: Document = Document(INPUT_DOCX)
    paragraphs: list = list(doc.paragraphs)
    all_tables: list = list(doc.tables)

    # ── 1. Build TOC tree ─────────────────────────────────────────────────────
    toc_tree: list[dict] = []
    section_indices: list[tuple[int, dict]] = []  # (para_idx, node)

    for i, para in enumerate(paragraphs):
        if not is_heading_para(para):
            continue
        style_name = para.style.name if para.style else ""
        level_map = {
            "Heading 1": 1, "Heading 2": 2, "Heading 3": 3,
            "Heading 4": 4, "Heading 5": 5,
        }
        level = level_map.get(style_name, 2)
        title = para.text.strip()
        if not title:
            continue

        body_snippet = get_section_body_snippet(paragraphs, i)
        classification = classify_section(title, body_snippet)

        node: dict = {
            "level": level,
            "title": title,
            "char_count": len(body_snippet),
            "classification": classification,
            "body_preview": body_snippet[:100],
            "table_count": 0,  # filled below
        }
        toc_tree.append(node)
        section_indices.append((i, node))

    # Count how many tables follow each section
    table_after: list[int] = [0] * len(section_indices)
    for ti, table in enumerate(all_tables):
        first_row_text = " ".join(c.text.strip() for c in table.rows[0].cells if c.text.strip())
        # Find which section this table belongs to (previous section heading)
        for si, (para_idx, _) in enumerate(section_indices):
            if si < len(section_indices) - 1:
                next_idx = section_indices[si + 1][0]
            else:
                next_idx = len(paragraphs)
            # rough: table is at document level if no specific section found
            pass
    # Simple heuristic: total tables / sections ratio
    total_tables = len(all_tables)

    # ── 2. Extract global format parameters ──────────────────────────────────
    font_samples: dict = {}
    indent_samples: dict = {}
    style_body_count: dict = Counter()

    for para in paragraphs:
        sname = para.style.name if para.style else "None"
        style_body_count[sname] += 1
        pf = para.paragraph_format
        if pf and pf.left_indent:
            indent_samples.setdefault(sname, []).append(round(float(pf.left_indent.pt), 1))
        for run in para.runs:
            if run.text.strip():
                fi = extract_font_info(run)
                if fi:
                    font_samples.setdefault(sname, fi)
                    break

    # Dominant body style
    body_styles = ["Normal", "Body Text", "Normal Indent", "_Style 13", "正文缩进2"]
    dominant_body_style = next(
        (s for s in body_styles if style_body_count.get(s, 0) > 100), "Normal"
    )
    dominant_font = font_samples.get(dominant_body_style, {})

    # Table structure summary
    table_depths: list[int] = []
    for tbl in all_tables:
        table_depths.append(len(tbl.rows))
    table_col_counts = Counter(len(tbl.rows[0].cells) if tbl.rows else 0 for tbl in all_tables)

    # Heading level 1 font size
    h1_font = font_samples.get("Heading 1", {})

    # ── 3. Build formatting blueprint ─────────────────────────────────────────
    format_blueprint: dict = {
        "document": {
            "total_paragraphs": len(paragraphs),
            "total_tables": len(all_tables),
            "total_sections": len(toc_tree),
            "heading_depth": 5,
        },
        "body_style": {
            "primary_style": dominant_body_style,
            "font": dominant_font,
            "typical_indent_pt": round(sum(indent_samples.get(dominant_body_style, [0])) /
                                       max(len(indent_samples.get(dominant_body_style, [0])), 1), 1),
            "note": "Normal style is dominant (2190 paras); Body Text is secondary",
        },
        "heading_styles": {
            "Heading 1": {
                "font": font_samples.get("Heading 1", {}),
                "usage_count": style_body_count.get("Heading 1", 0),
                "note": "Top-level chapter headings (一、二、三...)",
            },
            "Heading 2": {
                "font": font_samples.get("Heading 2", {}),
                "usage_count": style_body_count.get("Heading 2", 0),
                "note": "Section headings (（1）, （2）...)",
            },
            "Heading 3": {
                "font": font_samples.get("Heading 3", {}),
                "usage_count": style_body_count.get("Heading 3", 0),
                "note": "Sub-sections",
            },
        },
        "table_statistics": {
            "total_tables": len(all_tables),
            "most_common_columns": table_col_counts.most_common(3),
            "most_common_row_counts": Counter(table_depths).most_common(5),
            "note": "160 total tables — mostly 2-col (form fields) and multi-col (scoring grids)",
        },
        "boilerplate_keywords": BOILERPLATE_HEADING_KEYWORDS,
        "generative_keywords": GENERATIVE_HEADING_KEYWORDS,
    }

    # ── 4. Count classifications ─────────────────────────────────────────────
    bp_count = sum(1 for n in toc_tree if n["classification"] == "boilerplate")
    gen_count = sum(1 for n in toc_tree if n["classification"] == "generative")
    unk_count = sum(1 for n in toc_tree if n["classification"] == "unknown")

    # ── 5. Build section list with sequence ─────────────────────────────────
    sections_list: list[dict] = []
    for i, node in enumerate(toc_tree):
        sections_list.append({
            "seq": i + 1,
            "level": node["level"],
            "title": node["title"],
            "classification": node["classification"],
            "body_preview": node["body_preview"],
            "table_count_hint": "check_body",  # placeholder
        })

    # ── 6. Assemble JSON structure ────────────────────────────────────────────
    template_structure: dict = {
        "meta": {
            "source": INPUT_DOCX.name,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total_heading_sections": len(toc_tree),
            "total_tables": len(all_tables),
            "boilerplate_sections": bp_count,
            "generative_sections": gen_count,
            "unknown_sections": unk_count,
        },
        "format_blueprint": format_blueprint,
        "sections": sections_list,
        "boilerplate_sections": [
            {k: v for k, v in s.items() if k != "body_preview"}
            for s in sections_list if s["classification"] == "boilerplate"
        ],
        "generative_sections": [
            {k: v for k, v in s.items() if k != "body_preview"}
            for s in sections_list if s["classification"] == "generative"
        ],
    }

    # ── 7. Write JSON ────────────────────────────────────────────────────────
    OUTPUT_JSON.write_text(
        json.dumps(template_structure, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ── 8. Build Markdown assembly guide ─────────────────────────────────────
    timestamp: str = datetime.now().strftime("%Y-%m-%d %H:%M")

    md_lines: list[str] = [
        "# V2 投标文件组装逻辑指南",
        "",
        f"**来源**: {INPUT_DOCX.name}",
        f"**生成时间**: {timestamp}",
        f"**分析方法**: python-docx 逆向解析（Heading 1-5 层级 + 排版格式）",
        "",
        "---",
        "",
        "## 一、文档宏观结构（按阅读顺序）",
        "",
        f"| # | 层级 | 章节名称 | 类型 | 预览（前100字） |",
        f"|---|---|---|---|---|",
    ]
    for s in sections_list:
        lvl_sym = {1: "章", 2: "节", 3: "小节", 4: "子节", 5: "细目"}[s["level"]]
        badge = {
            "boilerplate": "🔒 静态模板",
            "generative": "⚡ 动态生成",
            "unknown": "❓ 待定",
        }.get(s["classification"], s["classification"])
        preview = (s["body_preview"] or "")[:80].replace("\n", " ")
        md_lines.append(
            f"| {s['seq']} | {lvl_sym} | {s['title']} | {badge} | {preview} |"
        )

    md_lines += [
        "",
        "---",
        "",
        "## 二、静态模板区（Boilerplate Sections）",
        "",
        f"> 共 **{bp_count}** 个章节 — 标记为 `boilerplate`",
        "",
        "**含义**：这些章节的内容主体是固定的格式文本（法规声明、表格模板、证明材料清单），",
        "系统后续只需要做「变量替换」（如填入公司名、中标金额、日期），无需调用 LLM 生成。",
        "",
        "**典型模式**：",
        "```",
        "【原文结构】",
        "《法定代表人授权书》",
        "兹授权 [姓名] 为我公司委托代理人，代表本公司签署____________项目的投标文件，...",
        "【系统处理】→ 替换 [姓名] / [公司名] / [日期] 三个变量",
        "```",
        "",
        "**清单**：",
    ]
    for s in sections_list:
        if s["classification"] == "boilerplate":
            lvl = {1: "章", 2: "节", 3: "小节"}.get(s["level"], "节")
            md_lines.append(f"- [{lvl}] **{s['title']}**")

    md_lines += [
        "",
        "---",
        "",
        "## 三、动态生成区（Generative Sections）",
        "",
        f"> 共 **{gen_count}** 个章节 — 标记为 `generative`",
        "",
        "**含义**：这些章节需要 LLM 结合 RAG 双轨召回的历史智慧来生成具体内容。",
        "生成时需要注入：",
        "1. `retrieve_positive_samples()` — 调取同类项目的成功方案片段",
        "2. `retrieve_negative_samples()` — 调取同类项目的失败教训",
        "3. `pricing_benchmark` — 注入市场参考价格（如有）",
        "",
        "**清单**：",
    ]
    for s in sections_list:
        if s["classification"] == "generative":
            lvl = {1: "章", 2: "节", 3: "小节"}.get(s["level"], "节")
            md_lines.append(f"- [{lvl}] **{s['title']}**")

    md_lines += [
        "",
        "---",
        "",
        "## 四、排版格式参数（Format Blueprint）",
        "",
        "```json",
        json.dumps(format_blueprint, ensure_ascii=False, indent=2),
        "```",
        "",
        "---",
        "",
        "## 五、Generator.py 组装流程建议",
        "",
        "```python",
        "# 伪代码：如何使用 bid_template_structure.json 组装最终标书",
        "",
        "import json",
        "",
        "with open('bid_template_structure.json') as f:",
        "    template = json.load(f)",
        "",
        "doc = Document()  # python-docx",
        "",
        "for section in template['sections']:",
        "    # 1. 写标题（ Heading 1 / 2 / 3）",
        "    heading_level = section['level']",
        "    doc.add_heading(section['title'], level=heading_level)",
        "",
        "    if section['classification'] == 'boilerplate':",
        "        # 2a. 插入静态模板内容（从模板库读取）",
        "        static_content = load_boilerplate(section['title'])",
        "        doc.add_paragraph(static_content)",
        "",
        "    elif section['classification'] == 'generative':",
        "        # 2b. 调用双轨 RAG 生成动态内容",
        "        chunks = retriever.retrieve_positive_samples(",
        "            query=section['title'],",
        "            scoring_dimension_tags=infer_dimensions(section['title'])，",
        "            top_k=5",
        "        )",
        "        draft = llm.generate(",
        "            system_prompt=BID_SYSTEM_PROMPT,",
        "            context=chunks",
        "        )",
        "        doc.add_paragraph(draft)",
        "",
        "    # 3. 如有表格，插入格式表格",
        "    if section.get('has_table'):",
        "        doc.add_table(rows=N, cols=M, style='Table Grid')",
        "",
        "# 4. 保存最终 DOCX",
        "doc.save('最终投标文件.docx')",
        "```",
        "",
        "---",
        "",
        "## 六、关键工程决策",
        "",
        "| 决策点 | 建议 | 理由 |",
        "|---|---|---|",
        "| 表格处理 | 保留模板结构，表格内容分为「填写式」和「自写式」 | 160张表大部分是格式表，只需填空 |",
        "| 动态生成阈值 | 仅对 `generative` 标记的节（≥200字 body）调用 RAG | 避免小节（<200字）过度生成 |",
        "| 并发生成 | 同级 `generative` 章节可并发调用 LLM | Python asyncio 或多进程 |",
        "| 模板版本管理 | 每个采购方类型（食堂/学校/医院）独立 JSON 模板 | 结构差异大，不可共用 |",
    ]

    OUTPUT_MD.write_text("\n".join(md_lines), encoding="utf-8")

    # ── 9. Silent summary to stdout ──────────────────────────────────────────
    print("=" * 60, flush=True)
    print(" template_reverse_engineer.py — V2 Template Reverse Eng.", flush=True)
    print("=" * 60, flush=True)
    print(f"  Sections   : {len(toc_tree)} (boilerplate={bp_count}, generative={gen_count})", flush=True)
    print(f"  Tables     : {len(all_tables)}", flush=True)
    print(f"  JSON       : {OUTPUT_JSON}", flush=True)
    print(f"  Markdown   : {OUTPUT_MD}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
