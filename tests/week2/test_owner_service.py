"""Tests for OwnerProfileService - TDD."""
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from app.core.week2_evaluation.owner_service import OwnerProfileService
from app.models.enums import RelationshipLevel


class TestOwnerProfileService:
    """TDD tests for OwnerProfileService."""

    def test_get_existing_owner_profile(self):
        """When owner exists in DB, return their profile."""
        # Arrange: mock DB session returning a known profile
        mock_db = MagicMock(spec=Session)
        mock_profile = MagicMock()
        mock_profile.owner_name = "某市政府"
        mock_profile.region = "杭州"
        mock_profile.relationship_level = RelationshipLevel.STRONG
        mock_profile.cooperation_count = 5
        mock_profile.preferred_styles = {"style": "高效务实", "tags": ["快速审批", "本地化"]}

        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_profile

        service = OwnerProfileService(mock_db)
        result = service.get_profile("某市政府", "杭州")

        assert result.owner_name == "某市政府"
        assert result.region == "杭州"
        assert result.relationship_level == RelationshipLevel.STRONG
        assert result.cooperation_count == 5
        assert result.preferred_styles == {"style": "高效务实", "tags": ["快速审批", "本地化"]}
        assert result.is_new_owner is False

    def test_get_nonexistent_owner_returns_default(self):
        """When owner not found, return neutral default profile."""
        mock_db = MagicMock(spec=Session)
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        service = OwnerProfileService(mock_db)
        result = service.get_profile("新业主公司", "北京")

        assert result.owner_name == "新业主公司"
        assert result.region == "北京"
        assert result.relationship_level == RelationshipLevel.NONE
        assert result.cooperation_count == 0
        assert result.preferred_styles is None
        assert result.is_new_owner is True

    def test_new_owner_is_marked_as_is_new(self):
        """Verify is_new_owner=True when profile not found."""
        mock_db = MagicMock(spec=Session)
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        service = OwnerProfileService(mock_db)
        result = service.get_profile("陌生业主", "上海")

        assert result.is_new_owner is True
        # All default values for a new owner
        assert result.relationship_level == RelationshipLevel.NONE
        assert result.cooperation_count == 0
