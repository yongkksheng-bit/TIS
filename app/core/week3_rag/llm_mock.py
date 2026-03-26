"""Mock LLM for testing RAG generation pipeline."""
import os
import hashlib
import random
from typing import Any


class MockResponse:
    """Standardized mock LLM response format."""

    def __init__(self, content: str, usage: dict[str, int] | None = None):
        self.content = content
        self.usage = usage or {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}


class MockDeepSeekLLM:
    """
    Deterministic mock for LLM generation (not embedding).
    Used by TechProposalGenerator in TDD.
    NEVER makes real API calls.
    """

    def __init__(self, model: str = "deepseek-chat"):
        self.model = model
        self.call_history: list[dict[str, Any]] = []

    def generate(
        self,
        prompt: str,
        mode: str = "auto",
        insider_notes: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> MockResponse:
        """
        Generate a deterministic mock response.
        - mode: 'auto' or 'guided'
        - insider_notes: list of strings (only used in guided mode)
        """
        # Record call for verification
        self.call_history.append({
            "prompt": prompt,
            "mode": mode,
            "insider_notes": insider_notes or [],
            "temperature": temperature,
        })

        # Deterministic content based on prompt
        prompt_hash = hashlib.md5(prompt.encode()).digest()
        seed = int.from_bytes(prompt_hash[:4], 'big') / (2**32)
        rng = random.Random(seed)

        # Build response content
        if mode == "guided" and insider_notes:
            # In guided mode, echo back the insider notes constraint
            content = f"[GUIDED MODE RESPONSE]\n内幕要点已被采纳：\n"
            for note in insider_notes:
                content += f"- {note}\n"
            content += f"\n基于以上约束的标书内容..."
        else:
            content = f"[AUTO MODE RESPONSE]\n这是一个模拟的投标技术标内容，对应提示词：{prompt[:50]}..."

        # Simulate token usage
        usage = {
            "prompt_tokens": len(prompt) // 4,
            "completion_tokens": len(content) // 4,
            "total_tokens": (len(prompt) + len(content)) // 4,
        }

        return MockResponse(content=content, usage=usage)

    def get_last_call(self) -> dict[str, Any] | None:
        """Return the last call record, for test assertions."""
        return self.call_history[-1] if self.call_history else None


def get_llm() -> MockDeepSeekLLM:
    """Factory: returns MockDeepSeekLLM for testing."""
    return MockDeepSeekLLM()
