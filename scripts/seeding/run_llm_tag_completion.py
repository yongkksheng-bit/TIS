"""P1: LLM Tag Completion for knowledge_chunks.

Fills in scoring_dimension_tags for chunks that have empty tags {}.
Uses deepseek-v4-flash (non-thinking, fast, cheap).

Usage:
    python -m scripts.seeding.run_llm_tag_completion --batch-size 50 --checkpoint-every 10
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from tenacity import Retrying, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ── Config ────────────────────────────────────────────────────────────────────
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"

# Checkpoint file
CHECKPOINT_FILE = Path("/tmp/llm_tag_checkpoint.json")

# Circuit breaker
MAX_CONSECUTIVE_FAILURES = 3

# Scoring dimensions (same as DIMENSION_KEYWORDS in historical_chunker.py)
DIMENSION_TAGS = [
    "食材溯源", "冷链管理", "卫生保障", "配送能力",
    "报价合理性", "服务方案", "企业资质", "历史业绩",
    "技术方案", "评分标准",
]

# Prompt for LLM
LLM_SYSTEM_PROMPT = (
    "你是招投标专家。根据文本内容，从以下10个评分维度中选择适用的标签："
    "食材溯源、冷链管理、卫生保障、配送能力、报价合理性、服务方案、"
    "企业资质、历史业绩、技术方案、评分标准。"
    "只输出JSON数组格式，禁止其他文字。\n"
    "格式: {\"tags\": [\"标签1\", \"标签2\"]}"
)

# ── Database helpers ────────────────────────────────────────────────────────────

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:Syk0215@tis_db:5432/canteen_system"
)


def get_db_connection():
    import psycopg2
    return psycopg2.connect(DB_URL)


def fetch_untagged_chunks(conn, limit=100, offset=0):
    """Fetch chunks with empty scoring_dimension_tags."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, content, char_length(content) as clen
        FROM knowledge_chunks
        WHERE NOT is_deprecated
          AND scoring_dimension_tags = '{}'
          AND char_length(content) >= 40
        ORDER BY char_length(content) DESC
        LIMIT %s OFFSET %s
    """, (limit, offset))
    rows = cur.fetchall()
    cur.close()
    return rows


def count_untagged(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*)
        FROM knowledge_chunks
        WHERE NOT is_deprecated
          AND scoring_dimension_tags = '{}'
          AND char_length(content) >= 40
    """)
    count = cur.fetchone()[0]
    cur.close()
    return count


def update_chunk_tags(conn, chunk_id: int, tags: list[str]):
    """Update scoring_dimension_tags for a single chunk."""
    cur = conn.cursor()
    cur.execute("""
        UPDATE knowledge_chunks
        SET scoring_dimension_tags = %s,
            updated_at = NOW()
        WHERE id = %s
    """, (tags, chunk_id))
    cur.close()


def commit(conn):
    conn.commit()


# ── LLM helpers ────────────────────────────────────────────────────────────────

_JSON_RE = __import__("re").compile(r"\{.*\}", __import__("re").DOTALL)


def extract_json(text: str) -> str:
    """Extract first JSON object from LLM response."""
    text = text.strip()
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        m = _JSON_RE.search(text)
        return m.group(0) if m else text


def call_deepseek_tag(content: str, api_key: str) -> list[str]:
    """Call DeepSeek to get dimension tags for content."""
    messages = [
        {"role": "system", "content": LLM_SYSTEM_PROMPT},
        {"role": "user", "content": f"【文本块】\n{content[:2000]}"},
    ]

    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 400,  # Enough for JSON with up to 10 tags
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    raw_content = data["choices"][0]["message"]["content"].strip()
    json_str = extract_json(raw_content)

    result = json.loads(json_str)
    tags = result.get("tags", [])

    # Validate tags are in DIMENSION_TAGS
    valid_tags = [t for t in tags if t in DIMENSION_TAGS]
    return valid_tags


def call_with_retry(content: str, api_key: str) -> list[str]:
    """Call DeepSeek with tenacity retry."""
    for attempt in Retrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.0, min=2, max=30),
        reraise=True,
    ):
        with attempt:
            return call_deepseek_tag(content, api_key)


# ── Checkpoint helpers ─────────────────────────────────────────────────────────

def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        return json.loads(CHECKPOINT_FILE.read_text())
    return {"processed": 0, "last_id": None, "consecutive_failures": 0, "errors": []}


def save_checkpoint(state: dict):
    CHECKPOINT_FILE.write_text(json.dumps(state, ensure_ascii=False))


# ── Main processing loop ──────────────────────────────────────────────────────

def process_chunk(chunk_id: int, content: str, api_key: str) -> list[str]:
    """Process single chunk and return tags."""
    return call_with_retry(content, api_key)


def run_completion(batch_size: int = 50, checkpoint_every: int = 10, dry_run: bool = False):
    if not DEEPSEEK_API_KEY:
        logger.error("DEEPSEEK_API_KEY not set")
        sys.exit(1)

    conn = get_db_connection()

    # Count total
    total = count_untagged(conn)
    logger.info(f"Total untagged chunks (>=80 chars): {total}")

    # Load checkpoint
    state = load_checkpoint()
    processed = state["processed"]
    last_id = state.get("last_id")
    consecutive_failures = state.get("consecutive_failures", 0)
    errors = state.get("errors", [])

    logger.info(f"Resuming from processed={processed}, last_id={last_id}, consecutive_failures={consecutive_failures}")

    if dry_run:
        logger.info("DRY RUN — fetching first batch only")
        chunks = fetch_untagged_chunks(conn, limit=batch_size, offset=0)
        for chunk_id, content, clen in chunks:
            logger.info(f"  Would process: id={chunk_id}, chars={clen}, content={content[:80]!r}")
        conn.close()
        return

    # Main loop
    offset = 0
    chunk_count = 0
    batch_count = 0

    while True:
        chunks = fetch_untagged_chunks(conn, limit=batch_size, offset=0)  # offset 0 = restart each time
        if not chunks:
            logger.info("No more chunks to process")
            break

        logger.info(f"Batch {batch_count + 1}: fetching {len(chunks)} chunks")

        for chunk_id, content, clen in chunks:
            chunk_count += 1

            try:
                tags = process_chunk(chunk_id, content, DEEPSEEK_API_KEY)

                if tags:
                    update_chunk_tags(conn, chunk_id, tags)
                    commit(conn)
                    logger.info(f"  [{chunk_count}] id={chunk_id} tagged={tags}")
                else:
                    logger.info(f"  [{chunk_count}] id={chunk_id} no tags (empty result)")

                consecutive_failures = 0
                processed += 1
                last_id = chunk_id

                # Checkpoint
                if chunk_count % checkpoint_every == 0:
                    save_checkpoint({
                        "processed": processed,
                        "last_id": last_id,
                        "consecutive_failures": consecutive_failures,
                        "errors": errors[-10:],  # Keep last 10 errors
                    })
                    logger.info(f"  Checkpoint saved: processed={processed}")

            except Exception as exc:
                consecutive_failures += 1
                error_msg = f"id={chunk_id}: {exc}"
                errors.append(error_msg)
                logger.warning(f"  [{chunk_count}] FAILED {error_msg}")

                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.error(f"CIRCUIT BREAKER: {consecutive_failures} consecutive failures. Pausing.")
                    save_checkpoint({
                        "processed": processed,
                        "last_id": last_id,
                        "consecutive_failures": consecutive_failures,
                        "errors": errors[-20:],
                    })
                    conn.close()
                    sys.exit(1)

        batch_count += 1

    # Final checkpoint
    save_checkpoint({
        "processed": processed,
        "last_id": last_id,
        "consecutive_failures": 0,
        "errors": [],
        "completed_at": datetime.utcnow().isoformat(),
    })

    logger.info(f"COMPLETE: {processed}/{total} chunks processed, {len(errors)} errors")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="P1: LLM Tag Completion")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for DB fetch")
    parser.add_argument("--checkpoint-every", type=int, default=10, help="Save checkpoint every N chunks")
    parser.add_argument("--dry-run", action="store_true", help="Dry run — show chunks without processing")
    args = parser.parse_args()

    run_completion(batch_size=args.batch_size, checkpoint_every=args.checkpoint_every, dry_run=args.dry_run)


if __name__ == "__main__":
    main()