"""Tests for OutcomeBook project_name-based lookup.

These tests verify that bid files can correctly resolve win_signal
by matching their project_name against the outcome_book.
"""
import csv
import tempfile
from pathlib import Path

import pytest

from scripts.seeding.utils.outcome_book import OutcomeBook


class TestOutcomeBookProjectLookup:
    """Test OutcomeBook.get_by_project_name() for bid file resolution."""

    @pytest.fixture
    def sample_csv(self, tmp_path: Path) -> Path:
        """Create a minimal outcome_book.csv for testing."""
        csv_path = tmp_path / "outcome_book.csv"
        content = """\
tender_file_name ,bid_file_name,project_name,our_bid_status,winning_price_rate,our_bid_rate,budget_amount
,2025_某项目_投标文件.docx,2025_某项目,won,95%,95%,9000000
,2025_另一个项目_投标文件.docx,2025_另一个项目,lost,,86%,5000000
"""
        csv_path.write_text(content, encoding="utf-8-sig")
        return csv_path

    @pytest.fixture
    def outcome_book(self, sample_csv: Path) -> OutcomeBook:
        """Load OutcomeBook from the sample CSV."""
        return OutcomeBook.from_csv(sample_csv)

    def test_get_by_project_name_finds_won_project(self, outcome_book: OutcomeBook):
        """Bid files for won projects should get positive win_signal."""
        result = outcome_book.get_by_project_name("2025_某项目")
        assert result is not None
        assert result["win_signal"] == "positive"
        assert result["our_bid_status"] == "won"

    def test_get_by_project_name_finds_lost_project(self, outcome_book: OutcomeBook):
        """Bid files for lost projects should get negative win_signal."""
        result = outcome_book.get_by_project_name("2025_另一个项目")
        assert result is not None
        assert result["win_signal"] == "negative"
        assert result["our_bid_status"] == "lost"

    def test_get_by_project_name_returns_none_for_unknown(self, outcome_book: OutcomeBook):
        """Unknown project names should return None."""
        result = outcome_book.get_by_project_name("不存在的项目")
        assert result is None

    def test_get_by_project_name_handles_suffix_stripping(self, outcome_book: OutcomeBook):
        """Project names with _投标文件 suffix should still match."""
        # DB stores project_name with _投标文件 suffix
        result = outcome_book.get_by_project_name("2025_某项目_投标文件")
        assert result is not None
        assert result["win_signal"] == "positive"


class TestBidFileResolution:
    """End-to-end test: verify bid files resolve win_signal correctly via project_name."""

    @pytest.fixture
    def outcome_csv(self, tmp_path: Path) -> Path:
        """Create outcome_book.csv matching real data patterns."""
        csv_path = tmp_path / "outcome_book.csv"
        # Line 2: 惠州 won - project_name='2025_惠州交通局食堂配送服务' (short, no suffix match)
        # Line 4: 粤北 won - project_name matches after stripping _投标文件
        content = """\
tender_file_name ,bid_file_name,project_name,our_bid_status,winning_price_rate,our_bid_rate,budget_amount
,2025_惠州市交通运输局交通大厦食堂管理和食材配送服务_投标文件.docx,2025_惠州交通局食堂配送服务,won,95%,95%,9000000
,2025_广东省粤北片区监狱（乐昌、韶关、武江、北江）2025-2026年度罪犯大宗生活物资（大米及食用油）采购项目_投标文件.docx,2025_广东省粤北片区监狱（乐昌、韶关、武江、北江）2025-2026年度罪犯大宗生活物资（大米及食用油）采购项目,won,88%,88%,15524924
,2025_监所羁押人员食堂食材配送服务采购项目_投标文件.docx,2025_监所羁押人员食堂食材配送服务采购项目,lost,,97%,13824000
"""
        csv_path.write_text(content, encoding="utf-8-sig")
        return csv_path

    @pytest.fixture
    def book(self, outcome_csv: Path) -> OutcomeBook:
        return OutcomeBook.from_csv(outcome_csv)

    def test_exact_project_name_match(self, book: OutcomeBook):
        """Projects with exact names should resolve directly."""
        result = book.get_by_project_name("2025_惠州交通局食堂配送服务")
        assert result is not None
        assert result["win_signal"] == "positive"

    def test_suffix_stripped_match(self, book: OutcomeBook):
        """DB stores '项目_投标文件' but outcome has '项目' - strip to match."""
        result = book.get_by_project_name(
            "2025_广东省粤北片区监狱（乐昌、韶关、武江、北江）2025-2026年度罪犯大宗生活物资（大米及食用油）采购项目_投标文件"
        )
        assert result is not None
        assert result["win_signal"] == "positive"

    def test_lost_project_match(self, book: OutcomeBook):
        """Lost project should resolve to negative."""
        result = book.get_by_project_name(
            "2025_监所羁押人员食堂食材配送服务采购项目_投标文件"
        )
        assert result is not None
        assert result["win_signal"] == "negative"