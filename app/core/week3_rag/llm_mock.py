"""Mock and real LLM clients for RAG generation pipeline."""
import os
import hashlib
import random
import json
import urllib.request
import urllib.error
from typing import Any


class MockResponse:
    """Standardized mock LLM response format."""

    def __init__(self, content: str, usage: dict[str, int] | None = None):
        self.content = content
        self.usage = usage or {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}


class RealDeepSeekResponse:
    """Wrapper for real API responses to match MockResponse interface."""

    def __init__(self, content: str, usage: dict[str, int] | None = None):
        self.content = content
        self.usage = usage or {}


class RealDeepSeekLLM:
    """
    Real DeepSeek API client for text generation.

    Controlled by USE_MOCK_LLM environment variable via get_llm() factory.
    When USE_MOCK_LLM=false and DEEPSEEK_API_KEY is set, this class is used.
    """

    BASE_URL = "https://api.deepseek.com"

    def __init__(self, model: str = "deepseek-chat", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY environment variable is not set. "
                "Set USE_MOCK_LLM=true to use mock mode for testing."
            )
        self.call_history: list[dict[str, Any]] = []

    def generate(
        self,
        prompt: str,
        mode: str = "auto",
        insider_notes: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_prompt: str | None = None,
    ) -> RealDeepSeekResponse:
        """
        Make a real API call to DeepSeek chat completion endpoint.

        Args:
            prompt: The user prompt text (combined prompt with system context)
            mode: 'auto' or 'guided' (for logging)
            insider_notes: insider notes for guided mode (for logging)
            temperature: sampling temperature
            max_tokens: max tokens in response
            system_prompt: explicit system prompt string (preferred over internal building)

        Returns:
            RealDeepSeekResponse with content and token usage
        """
        if system_prompt:
            system_content = system_prompt
        else:
            system_content = (
                "你是一位专业的政府采购投标技术标撰写助手。"
                if mode == "auto"
                else "你是一位专业的政府采购投标技术标撰写助手，内幕信息专家。"
            )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ]

        # Build request
        url = f"{self.BASE_URL}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(
                f"DeepSeek API error {e.code}: {error_body}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error calling DeepSeek API: {e.reason}") from e

        # Extract response
        choices = result.get("choices", [])
        if not choices:
            raise RuntimeError(f"DeepSeek API returned no choices: {result}")

        content = choices[0].get("message", {}).get("content", "")
        usage = result.get("usage", {})

        self.call_history.append({
            "prompt": prompt,
            "mode": mode,
            "insider_notes": insider_notes or [],
            "temperature": temperature,
        })

        return RealDeepSeekResponse(content=content, usage=usage)

    def get_last_call(self) -> dict[str, Any] | None:
        """Return the last call record."""
        return self.call_history[-1] if self.call_history else None


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
        seed = int.from_bytes(prompt_hash[:4], "big") / (2**32)
        rng = random.Random(seed)

        # Build response content
        if mode == "guided" and insider_notes:
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


def get_llm() -> RealDeepSeekLLM | MockDeepSeekLLM:
    """
    Factory: returns RealDeepSeekLLM when USE_MOCK_LLM=false and API key is set,
    otherwise returns MockDeepSeekLLM for testing.

    Set env var USE_MOCK_LLM=false and DEEPSEEK_API_KEY=<your-key> to use real API.
    """
    use_mock = os.environ.get("USE_MOCK_LLM", "true").lower() == "true"
    if use_mock:
        return MockDeepSeekLLM()
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise ValueError(
            "USE_MOCK_LLM=false but DEEPSEEK_API_KEY is not set. "
            "Either set DEEPSEEK_API_KEY or set USE_MOCK_LLM=true."
        )
    return RealDeepSeekLLM(api_key=api_key)
