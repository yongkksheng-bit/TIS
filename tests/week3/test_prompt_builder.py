import pytest
from app.core.week3_rag.prompt_builder import (
    TechProposalPromptBuilder,
    AUTO_KEYWORDS,
    GUIDED_KEYWORDS,
)
from app.schemas.rag import ChunkNode


@pytest.fixture
def builder():
    return TechProposalPromptBuilder()


@pytest.fixture
def sample_project_info():
    return {
        "project_name": "某市政府食堂配送项目",
        "owner_unit": "某市人民政府办公室",
        "project_type": "food",
        "region": "北京",
        "budget_amount": 5000000.00,
        "bid_open_date": "2026-04-15",
    }


@pytest.fixture
def sample_chunks():
    return [
        ChunkNode(
            text="冷链配送需保证温度在0-4摄氏度之间",
            chunk_index=0,
            char_length=20,
            metadata={"source": "knowledge_base_1", "chunk_type": "technical"},
        ),
        ChunkNode(
            text="应急预案需包括车辆故障、交通事故等场景",
            chunk_index=1,
            char_length=22,
            metadata={"source": "knowledge_base_2", "chunk_type": "technical"},
        ),
    ]


class TestBuildSystemPrompt:
    def test_auto_mode_system_prompt_contains_standardization_keywords(
        self, builder, sample_project_info
    ):
        """AUTO mode system prompt must contain standardization/compliance keywords."""
        prompt = builder.build_system_prompt(
            generation_mode="auto",
            project_type="食材配送"
        )
        # Check for at least 2 AUTO keywords (template has 标准化, 合规要求)
        found = [kw for kw in AUTO_KEYWORDS if kw in prompt]
        assert len(found) >= 2, f"Expected ≥2 AUTO keywords, found {found}"

    def test_guided_mode_system_prompt_contains_differentiation_keywords(
        self, builder, sample_project_info
    ):
        """GUIDED mode system prompt must contain differentiation/competitive keywords."""
        prompt = builder.build_system_prompt(
            generation_mode="guided",
            insider_notes="必须使用双汇冷鲜肉，避开周一配送",
            project_type="食材配送"
        )
        # Check for at least 3 GUIDED keywords
        found = [kw for kw in GUIDED_KEYWORDS if kw in prompt]
        assert len(found) >= 3, f"Expected ≥3 GUIDED keywords, found {found}"

    def test_auto_mode_never_contains_insider_notes(self, builder):
        """AUTO mode system prompt must NOT include insider_notes."""
        prompt = builder.build_system_prompt(
            generation_mode="auto",
            insider_notes="这条不应该出现",
        )
        assert "这条不应该出现" not in prompt
        assert "内幕" not in prompt

    def test_guided_mode_rejects_empty_insider_notes(self, builder):
        """GUIDED mode without insider_notes must raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            builder.build_system_prompt(generation_mode="guided")
        assert "insider_notes" in str(exc_info.value).lower()

    def test_guided_mode_rejects_whitespace_insider_notes(self, builder):
        """GUIDED mode with blank insider_notes must raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            builder.build_system_prompt(generation_mode="guided", insider_notes="   ")
        assert "insider_notes" in str(exc_info.value).lower()

    def test_guided_mode_includes_insider_notes_in_prompt(self, builder):
        """GUIDED mode must embed insider_notes verbatim in system prompt."""
        notes = "必须使用双汇品牌，避开高峰时段"
        prompt = builder.build_system_prompt(
            generation_mode="guided",
            insider_notes=notes,
        )
        assert notes in prompt
        assert "内幕要点" in prompt or "独家竞争优势" in prompt

    def test_auto_and_guided_prompts_are_different(self, builder):
        """AUTO and GUIDED system prompts must be structurally different."""
        auto = builder.build_system_prompt(generation_mode="auto")
        guided = builder.build_system_prompt(
            generation_mode="guided",
            insider_notes="测试内幕",
        )
        assert auto != guided

    def test_unknown_mode_raises_value_error(self, builder):
        """Unknown generation_mode raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            builder.build_system_prompt(generation_mode="invalid")
        assert "Unknown generation_mode" in str(exc_info.value)

    def test_mode_keywords_returns_correct_list(self, builder):
        """mode_keywords() returns the correct keyword list per mode."""
        auto_kw = builder.mode_keywords("auto")
        guided_kw = builder.mode_keywords("guided")
        assert auto_kw == AUTO_KEYWORDS
        assert guided_kw == GUIDED_KEYWORDS


class TestBuildUserPrompt:
    def test_context_chunks_wrapped_in_xml_tags(
        self, builder, sample_project_info, sample_chunks
    ):
        """context_chunks must appear inside <reference_documents> tags."""
        prompt = builder.build_user_prompt(
            project_info=sample_project_info,
            context_chunks=sample_chunks,
            target_section="冷链配送方案",
        )
        assert "<reference_documents>" in prompt
        assert "</reference_documents>" in prompt

    def test_chunk_texts_extracted_correctly(
        self, builder, sample_project_info, sample_chunks
    ):
        """ChunkNode.text is extracted verbatim into the XML context."""
        prompt = builder.build_user_prompt(
            project_info=sample_project_info,
            context_chunks=sample_chunks,
            target_section="第一章",
        )
        for chunk in sample_chunks:
            assert chunk.text in prompt

    def test_project_info_included_in_prompt(
        self, builder, sample_project_info, sample_chunks
    ):
        """User prompt contains project_name, owner_unit, region, etc."""
        prompt = builder.build_user_prompt(
            project_info=sample_project_info,
            context_chunks=sample_chunks,
            target_section="技术方案",
        )
        assert sample_project_info["project_name"] in prompt
        assert sample_project_info["owner_unit"] in prompt
        assert sample_project_info["region"] in prompt

    def test_target_section_included(
        self, builder, sample_project_info, sample_chunks
    ):
        """User prompt includes the target_section."""
        target = "第一章：冷链配送方案"
        prompt = builder.build_user_prompt(
            project_info=sample_project_info,
            context_chunks=sample_chunks,
            target_section=target,
        )
        assert target in prompt

    def test_empty_chunks_still_produces_valid_prompt(
        self, builder, sample_project_info
    ):
        """Empty context_chunks produces a structurally valid prompt."""
        prompt = builder.build_user_prompt(
            project_info=sample_project_info,
            context_chunks=[],
            target_section="测试章节",
        )
        assert "<reference_documents>" in prompt
        assert "</reference_documents>" in prompt
        assert "测试章节" in prompt

    def test_chunks_without_metadata_still_work(
        self, builder, sample_project_info
    ):
        """ChunkNodes without metadata still produce valid output."""
        chunks = [
            ChunkNode(text="纯文本内容", chunk_index=0, char_length=6, metadata={}),
        ]
        prompt = builder.build_user_prompt(
            project_info=sample_project_info,
            context_chunks=chunks,
            target_section="测试",
        )
        assert "纯文本内容" in prompt
