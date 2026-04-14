#!/usr/bin/env python3
"""
deep_bid_analyzer.py — V2 Bid Document Deep Analysis (Map-Reduce)

Engineering constraint:
  ALL output files stay within D:/tis_project/scripts/deep_bid_analysis/
  No writes to /tmp/, project root, or business code directories.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ── API Config ────────────────────────────────────────────────────────────────
DEEPSEEK_API_KEY: str = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE: str = "https://api.deepseek.com"
MODEL: str = "deepseek-chat"

# ── Path constraints (all I/O stays in scripts/deep_bid_analysis/) ──────────────
SCRIPT_DIR: Path = Path(__file__).parent.resolve()
INPUT_DOCX: Path = Path("/tmp/historical_documents/2025_惠州市交通运输局交通大厦食堂管理和食材配送服务_投标文件.docx")
OUTPUT_MD: Path = SCRIPT_DIR / "V2_bid_domain_analysis.md"
PROGRESS_FILE: Path = SCRIPT_DIR / "_progress.json"
CHUNKS_DIR: Path = SCRIPT_DIR / "_chapter_chunks"
CHUNKS_DIR.mkdir(exist_ok=True)

# ── LLM Prompt ────────────────────────────────────────────────────────────────
SYSTEM_PROMPT: str = (
    "你是一位招投标领域的资深专家。你的任务是对给定的一个投标文件章节进行深度分析，"
    "并按以下三个维度提炼信息：\n"
    "1. 核心痛点（Core Pain Points）：招标方在这一章节中强调的关键需求、约束条件或潜在风险\n"
    "2. 技术响应指标（Technical Response Indicators）：投标方需要在技术方案中具体回应的指标、数据或标准\n"
    "3. 竞争优势（Competitive Advantages）：基于这一章节，投标人可以突出展示的差异化优势\n"
    "请用简洁的要点（bullet points）输出，每个维度3-5条。使用中文。"
)

# ── Chapter heading patterns ──────────────────────────────────────────────────
CHAPTER_PATTERNS: list[re.Pattern] = [
    re.compile(r"^第[一二三四五六七八九十百零0-9]+章[\s　·].*"),
    re.compile(r"^[一二三四五六七八九十零]+、[\s　].*"),
    re.compile(r"^[0-9]+[.、][\s　].*"),
]


def is_chapter_heading(line: str) -> bool:
    s = line.strip()
    if len(s) < 4 or len(s) > 60:
        return False
    return any(pat.match(s) for pat in CHAPTER_PATTERNS)


def extract_chapters(path: Path) -> list[dict]:
    """Load DOCX and split into chapter blocks using heading detection."""
    from docx import Document

    doc = Document(path)
    chapters: list[dict] = []
    current_title: str = "_PRE_CHAPTER_"
    current_lines: list[str] = []

    for para in doc.paragraphs:
        text: str = para.text.strip()
        if not text:
            continue
        if is_chapter_heading(text):
            if current_lines:
                chapters.append({
                    "title": current_title,
                    "body": "\n".join(current_lines),
                })
                current_lines.clear()
            current_title = text
        else:
            current_lines.append(text)

    if current_lines:
        chapters.append({
            "title": current_title,
            "body": "\n".join(current_lines),
        })

    # Filter out chapters that are too short to be meaningful
    return [c for c in chapters if len(c["body"]) >= 100]


def call_deepseek(chapter: dict, retry: int = 3) -> dict:
    """Call DeepSeek chat API to analyze a chapter. Returns dict."""
    url: str = f"{DEEPSEEK_BASE}/v1/chat/completions"
    headers: dict = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    user_prompt: str = (
        f"【章节标题】{chapter['title']}\n\n"
        f"【章节内容摘要（前2000字）】\n{chapter['body'][:2000]}"
    )
    payload: dict = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 800,
    }

    last_err: Exception | None = None
    for attempt in range(retry):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            if resp.status_code == 529:
                wait: float = (2 ** attempt) * 2.0
                print(f"  [rate-limit 529 — retry {attempt+1}/{retry} in {wait}s...]", flush=True)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            content: str = data["choices"][0]["message"]["content"]
            return {"ok": True, "content": content}
        except Exception as exc:
            last_err = exc
            wait = (2 ** attempt)
            time.sleep(wait)

    return {"ok": False, "error": str(last_err)}


def build_markdown(chapters: list[dict], results: list[dict]) -> str:
    """Build the final aggregated Markdown report."""
    timestamp: str = datetime.now().strftime("%Y-%m-%d %H:%M")
    ok_count: int = sum(1 for r in results if r["ok"])

    lines: list[str] = [
        "# V2 投标文件深度分析报告",
        "",
        f"**来源**: 2025年惠州市交通运输局交通大厦食堂管理和食材配送服务 投标文件",
        f"**生成时间**: {timestamp}",
        f"**分析章节数**: {len(chapters)}（成功: {ok_count}，失败: {len(chapters)-ok_count}）",
        "**分析方法**: DeepSeek Chat API (deepseek-chat, temperature=0.3)",
        "",
        "---",
        "",
    ]

    for ch, res in zip(chapters, results):
        status: str = "✅" if res["ok"] else f"❌ ({str(res.get('error', 'unknown'))[:50]})"
        lines.append(f"## [{status}] {ch['title']}")
        lines.append("")
        if res["ok"]:
            lines.append(res["content"].strip())
        else:
            lines.append(f"> **分析失败**: {res.get('error', 'unknown')}")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    print("=" * 60, flush=True)
    print(" deep_bid_analyzer.py — Map-Reduce Bid Analysis V2", flush=True)
    print("=" * 60, flush=True)
    print(f"  Output dir : {SCRIPT_DIR}", flush=True)
    print(f"  Input DOCX : {INPUT_DOCX}", flush=True)
    print(f"  API base   : {DEEPSEEK_BASE}", flush=True)

    if not DEEPSEEK_API_KEY:
        print("FATAL: DEEPSEEK_API_KEY not set in environment", flush=True)
        sys.exit(1)

    if not INPUT_DOCX.exists():
        print(f"FATAL: DOCX not found at {INPUT_DOCX}", flush=True)
        sys.exit(1)

    # ── Phase 1: Extract (Map) ─────────────────────────────────────────────
    print("\n[Phase 1/3] Extracting chapters from DOCX...", flush=True)
    chapters: list[dict] = extract_chapters(INPUT_DOCX)
    print(f"  → Found {len(chapters)} chapters", flush=True)

    for i, ch in enumerate(chapters):
        slug: str = re.sub(r"[^\w\u4e00-\u9fff]", "_", ch["title"][:20])
        chunk_path: Path = CHUNKS_DIR / f"chapter_{i:02d}_{slug}.json"
        chunk_path.write_text(json.dumps(ch, ensure_ascii=False), encoding="utf-8")
        print(f"  [{i+1:02d}/{len(chapters)}] {ch['title'][:50]}", flush=True)

    # ── Phase 2: Analyze (Reduce) ──────────────────────────────────────────
    print(f"\n[Phase 2/3] Calling DeepSeek API for each chapter...", flush=True)
    results: list[dict] = []
    for i, ch in enumerate(chapters):
        short: str = ch["title"][:40]
        print(f"  [{i+1:02d}/{len(chapters)}] {short}... ", end="", flush=True)
        result: dict = call_deepseek(ch)
        results.append(result)
        # Silent checkpoint
        PROGRESS_FILE.write_text(
            json.dumps({"done": i+1, "total": len(chapters)}),
            encoding="utf-8",
        )
        print("OK" if result["ok"] else f"FAIL({str(result.get('error','?'))[:30]})", flush=True)

    # ── Phase 3: Write report ──────────────────────────────────────────────
    print(f"\n[Phase 3/3] Writing aggregated Markdown report...", flush=True)
    md: str = build_markdown(chapters, results)
    OUTPUT_MD.write_text(md, encoding="utf-8")

    ok: int = sum(1 for r in results if r["ok"])
    print("\n" + "=" * 60, flush=True)
    print(f" ✅ DONE — {ok}/{len(chapters)} chapters analyzed successfully", flush=True)
    print(f" 📄 Report → {OUTPUT_MD}", flush=True)
    print(f" 📦 Chunks → {CHUNKS_DIR}/ ({len(list(CHUNKS_DIR.glob('*.json')))} files)", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
