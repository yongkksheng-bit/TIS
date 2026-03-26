"""TDD tests for Mock LLM."""
import pytest
from app.core.week3_rag.llm_mock import MockDeepSeekLLM, MockResponse, get_llm


class TestMockDeepSeekLLM:
    def test_generate_returns_mock_response(self):
        """generate() returns a MockResponse with content and usage."""
        mock = MockDeepSeekLLM()
        response = mock.generate("写一个配送方案")
        assert isinstance(response, MockResponse)
        assert hasattr(response, 'content')
        assert hasattr(response, 'usage')

    def test_generate_content_is_string(self):
        """Response content is a non-empty string."""
        mock = MockDeepSeekLLM()
        response = mock.generate("测试提示词")
        assert isinstance(response.content, str)
        assert len(response.content) > 0

    def test_generate_usage_has_token_counts(self):
        """Response usage dict contains token counts."""
        mock = MockDeepSeekLLM()
        response = mock.generate("测试")
        assert 'prompt_tokens' in response.usage
        assert 'completion_tokens' in response.usage
        assert 'total_tokens' in response.usage

    def test_auto_mode_response(self):
        """Auto mode generates content without insider notes."""
        mock = MockDeepSeekLLM()
        response = mock.generate(prompt="技术标", mode="auto")
        assert "[AUTO MODE" in response.content

    def test_guided_mode_includes_insider_notes(self):
        """Guided mode content reflects insider notes."""
        mock = MockDeepSeekLLM()
        notes = ["使用双汇品牌", "避开高峰时段"]
        response = mock.generate(
            prompt="配送方案",
            mode="guided",
            insider_notes=notes
        )
        assert "GUIDED MODE RESPONSE" in response.content
        assert "内幕要点已被采纳" in response.content

    def test_call_history_recorded(self):
        """Each generate() call is recorded in history."""
        mock = MockDeepSeekLLM()
        mock.generate("call 1", mode="auto")
        mock.generate("call 2", mode="guided", insider_notes=["note"])
        assert len(mock.call_history) == 2
        assert mock.call_history[0]["prompt"] == "call 1"
        assert mock.call_history[1]["insider_notes"] == ["note"]

    def test_get_last_call_returns_correct_record(self):
        """get_last_call() returns the most recent call."""
        mock = MockDeepSeekLLM()
        mock.generate("first")
        mock.generate("second")
        last = mock.get_last_call()
        assert last["prompt"] == "second"

    def test_temperature_parameter_accepted(self):
        """generate() accepts temperature parameter without error."""
        mock = MockDeepSeekLLM()
        r = mock.generate("test", temperature=0.5)
        assert r.content is not None

    def test_deterministic_same_prompt_same_output(self):
        """Same prompt always produces same content (within same Mock instance)."""
        mock = MockDeepSeekLLM()
        r1 = mock.generate("恒定性")
        r2 = mock.generate("恒定性")
        assert r1.content == r2.content


class TestLLMFactory:
    def test_get_llm_returns_mock(self):
        """Factory returns MockDeepSeekLLM instance."""
        llm = get_llm()
        assert isinstance(llm, MockDeepSeekLLM)
