"""Unified LLM Factory — Multi-Provider High Availability Architecture.

Supports DeepSeek (OpenAI SDK) and MiniMax (Anthropic SDK compatible mode).
Routing is controlled by ACTIVE_LLM_PROVIDER environment variable.

Usage:
    from app.core.llm_factory import generate_json_insights

    messages = [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "分析以下文本：..."},
    ]
    result = generate_json_insights(messages)  # returns dict

Environment variables:
    ACTIVE_LLM_PROVIDER   — "deepseek" | "minimax" (default: deepseek)
    DEEPSEEK_API_KEY      — API key for DeepSeek
    MINIMAX_API_KEY       — API key for MiniMax
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

import requests
from tenacity import (
    Retrying,
    RetryError,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_result,
)

logger = logging.getLogger(__name__)

# ── Provider config ──────────────────────────────────────────────────────────

PROVIDER_DEEPSEEK = "deepseek"
PROVIDER_MINIMAX = "minimax"

DEEPSEEK_CONFIG = {
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-v4-flash",      # Non-thinking, fast, cheap (1元/百万 in, 2元/百万 out)
    "model_pro": "deepseek-v4-pro",    # Thinking mode,限时2.5折 (3元/百万 in, 6元/百万 out, 至2026/05/05)
    "reasoning_effort": "high",        # Default reasoning effort for deepseek-v4-pro
}

MINIMAX_CONFIG = {
    "base_url": "https://api.minimaxi.com/anthropic",
    "model": "MiniMax-M2.7",   # Latest flagship model
    "temperature": 1.0,        # Per official docs
    "top_p": 0.95,             # Per official docs
    "max_tokens": 2048,        # Generous output budget
}


# ── JSON extraction helpers ────────────────────────────────────────────────

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_THINKING_RE = re.compile(r"<think>[\s\S]*?</think>", re.MULTILINE)


def _extract_json(raw_text: str) -> str:
    """
    Physically extract the first JSON object from raw LLM output.

    Extraction pipeline:
      1. Strip all <think>...</think> thinking blocks (M2.7 multi-block format).
      2. Strip markdown code fences.
      3. Use regex \{.*\} with DOTALL to extract first JSON object.

    This ensures json.loads() receives ONLY the raw JSON — no markdown,
    no thinking tags, no explanatory text.
    """
    text = raw_text.strip()

    # Step 1: Physically remove ALL <thinking> blocks
    text = _THINKING_RE.sub("", text)

    # Fast path: if it's valid JSON already, return as-is
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Step 2: Extract first {...} block
    m = _JSON_RE.search(text)
    if m:
        return m.group(0)

    # Last resort: return stripped text and let json.loads fail naturally
    return text


# ── Provider call functions ────────────────────────────────────────────────

def _call_deepseek(
    messages: list[dict[str, str]],
    api_key: str,
    model: str,
    base_url: str,
    temperature: float = 0.3,
    max_tokens: int = 600,
    reasoning_effort: Optional[str] = None,
    top_p: Optional[float] = None,  # Ignored for DeepSeek, kept for interface compatibility
) -> dict[str, Any]:
    """
    Call DeepSeek /v1/chat/completions (OpenAI SDK-compatible).

    Supports deepseek-v4-flash (non-thinking) and deepseek-v4-pro (thinking mode).
    For thinking mode, pass reasoning_effort="low"|"medium"|"high" and model="deepseek-v4-pro".

    Uses OpenAI client library for proper SDK support.
    """
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)

    extra_body: dict[str, Any] = {}
    if reasoning_effort:
        extra_body["reasoning_effort"] = reasoning_effort
        extra_body["thinking"] = {"type": "enabled"}

    extra_kwargs: dict[str, Any] = {"extra_body": extra_body} if extra_body else {}

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
        **extra_kwargs,
    )

    return {"content": response.choices[0].message.content}


def _call_minimax(
    messages: list[dict[str, str]],
    api_key: str,
    model: str,
    base_url: str,
    temperature: float = 1.0,
    top_p: float = 0.95,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    """
    Call MiniMax via Anthropic SDK-compatible endpoint.

    Official Anthropic-compatible API for MiniMax-M2.7:
      POST https://api.minimaxi.com/anthropic/v1/messages
    Roles are passed as-is; system messages are included in messages array.
    """
    url = f"{base_url.rstrip('/')}/v1/messages"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": model,
        "messages": messages,   # [{"role": "system"|"user"|"assistant", "content": "..."}]
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()

    data = resp.json()
    # M2.7 returns {"content": [{"type": "text", "text": "{...}"}, {"type": "thinking", ...}]}
    # Also handles flat format {"thinking":..., "text":...} from some responses
    content_blocks = data.get("content", [])
    text = ""
    for block in content_blocks:
        if isinstance(block, dict):
            # Priority: typed "text" block (M2.7 standard format)
            if block.get("type") == "text" and "text" in block:
                text = block.get("text", "")
                break
            # Fallback: flat block with "text" key but no "type" field (M2.7 alternative)
            elif "text" in block and "type" not in block:
                text = block.get("text", "")
                break
    if not text:
        text = data.get("content", "")
        if isinstance(text, list):
            text = " ".join(b.get("text", "") for b in text if isinstance(b, dict)) or str(data)
        elif not isinstance(text, str):
            text = str(data)
    return {"content": text}


# ── Low-level HTTP call wrapped with tenacity retry ────────────────────────

_M网络_errors = (
    requests.ConnectionError,
    requests.Timeout,
    requests.HTTPError,
)


def _retrying_call(
    call_fn,
    *args,
    max_retries: int = 3,  # Circuit breaker: 3 attempts then fail fast
    **kwargs,
) -> dict[str, Any]:
    """
    Execute call_fn(*args, **kwargs) with tenacity retry.
    Retries on network errors and 5xx HTTP responses.
    """
    for attempt in Retrying(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1.0, min=1, max=30),
        retry=retry_if_exception_type(requests.ConnectionError)
              | retry_if_exception_type(requests.Timeout)
              | retry_if_result(lambda e: isinstance(e, requests.HTTPError) and (getattr(e.response, "status_code", 0) >= 400)),  # 429 + 5xx with backoff
        reraise=True,
        before_sleep=lambda retry_state: logger.warning(
            "Retry attempt %d/%d after %ds — %s",
            retry_state.attempt_number,
            max_retries,
            retry_state.next_action.sleep if retry_state.next_action else 0,
            retry_state.outcome.exception() if retry_state.outcome else None,
        ),
    ):
        with attempt:
            return call_fn(*args, **kwargs)

    # Should not reach here — Retrying.reraise=True ensures last exception propagates
    raise RuntimeError("Unreachable")


# ── Public API ──────────────────────────────────────────────────────────────

def generate_json_insights(
    messages: list[dict[str, str]],
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> dict[str, Any]:
    """
    Call the active LLM provider to generate structured JSON insights.

    Args:
        messages: List of {"role": "system"|"user"|"assistant", "content": "..."} dicts.
                  System prompt should be the FIRST message.
        provider: Override ACTIVE_LLM_PROVIDER ("deepseek" | "minimax").
                  If None, reads from ACTIVE_LLM_PROVIDER env var.
        model: Override model name. If None, uses provider default.
        temperature: Override sampling temperature. If None, uses provider default.
        max_tokens: Max tokens in response. If None, uses provider default.

    Returns:
        Parsed JSON dict from the LLM response.

    Raises:
        ValueError: If required API key is missing or provider is unknown.
        RuntimeError: If all retry attempts fail.
    """
    # ── Resolve provider ────────────────────────────────────────────────────
    active = provider or os.environ.get("ACTIVE_LLM_PROVIDER", PROVIDER_DEEPSEEK)

    if active == PROVIDER_DEEPSEEK:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY is not set. "
                "Set it in .env or export it to your environment."
            )
        cfg = DEEPSEEK_CONFIG
        temperature = temperature if temperature is not None else 0.3
        max_tokens = max_tokens if max_tokens is not None else 600
        call_fn = _call_deepseek

    elif active == PROVIDER_MINIMAX:
        api_key = os.environ.get("MINIMAX_API_KEY", "")
        if not api_key:
            raise ValueError(
                "MINIMAX_API_KEY is not set. "
                "Set it in .env or export it to your environment."
            )
        cfg = MINIMAX_CONFIG
        temperature = temperature if temperature is not None else cfg["temperature"]
        max_tokens = max_tokens if max_tokens is not None else cfg["max_tokens"]
        call_fn = _call_minimax

    else:
        raise ValueError(
            f"Unknown ACTIVE_LLM_PROVIDER: {active!r}. "
            f"Expected one of: {PROVIDER_DEEPSEEK!r}, {PROVIDER_MINIMAX!r}"
        )

    model_name = model or cfg["model"]
    base_url = cfg["base_url"]
    top_p = cfg.get("top_p", 0.95) if active == PROVIDER_MINIMAX else None
    reasoning_effort = cfg.get("reasoning_effort") if active == PROVIDER_DEEPSEEK else None

    try:
        raw = _retrying_call(
            call_fn,
            messages=messages,
            api_key=api_key,
            model=model_name,
            base_url=base_url,
            temperature=temperature,
            top_p=top_p if active == PROVIDER_MINIMAX else None,
            max_tokens=max_tokens,
            max_retries=3,  # Match circuit breaker limit
            reasoning_effort=reasoning_effort,
        )
        content: str = raw["content"].strip()

        # ── Physical JSON extraction ─────────────────────────────────────
        content = _extract_json(content)

        # Strip markdown code fences if present
        if content.startswith("```"):
            parts = content.split("```", 2)
            if len(parts) >= 3:
                content = parts[1].strip()
                # Remove optional language tag
                if content.startswith("json"):
                    content = content[4:].strip()
            else:
                content = parts[1].strip() if len(parts) == 2 else content

        result = json.loads(content)

        # Key normalization
        if "technical_response_indicators" in result and "technical_indicators" not in result:
            result["technical_indicators"] = result.pop("technical_response_indicators")

        return result

    except (json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError(
            f"LLM returned non-JSON after all retries: {type(exc).__name__}: {exc}"
        ) from exc
    except RetryError as exc:
        raise RuntimeError(
            f"LLM call failed after max retries: {exc}"
        ) from exc


def generate_insights_from_text(
    text: str,
    system_prompt: str,
    provider: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    """
    Convenience wrapper: build messages from (system_prompt, text) and call
    generate_json_insights. Returns None on complete failure.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"【文本块】\n{text[:2500]}"},
    ]
    try:
        return generate_json_insights(
            messages=messages,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        logger.error("generate_insights_from_text failed: %s", str(exc))
        return None
