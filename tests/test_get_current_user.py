"""TDD Tests for get_current_user dependency - B.2 JWT Middleware."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    def test_no_token_dev_mode_returns_user_id_1(self):
        """No Authorization header + DEV_MODE=true → user id=1 from DB."""
        from app.core.security import get_current_user
        from app.config import settings

        # Mock settings with DEV_MODE enabled
        with patch.object(settings, 'DEV_MODE', True):
            # Mock the DB query to return user id=1
            mock_user = MagicMock()
            mock_user.id = 1
            mock_user.username = "specialist"
            mock_user.email = "specialist@tis.local"

            mock_db = MagicMock()
            mock_query = MagicMock()
            mock_query.filter.return_value.first.return_value = mock_user
            mock_db.query.return_value = mock_query

            with patch('app.core.security._get_db_session', return_value=mock_db):
                mock_request = MagicMock()
                mock_request.headers = {}

                user = get_current_user(request=mock_request)

                assert user.id == 1
                assert user.username == "specialist"

    def test_valid_token_returns_real_user(self):
        """Valid JWT token → actual user from DB."""
        from app.core.security import get_current_user
        from app.config import settings
        import jwt

        # Create a valid JWT token
        payload = {
            "sub": "1",
            "username": "specialist",
            "email": "specialist@test.com",
            "exp": 9999999999  # Far future
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

        # Mock settings with DEV_MODE disabled
        with patch.object(settings, 'DEV_MODE', False):
            mock_request = MagicMock()
            mock_request.headers = {"Authorization": f"Bearer {token}"}

            user = get_current_user(request=mock_request)

            assert user.id == 1
            assert user.username == "specialist"

    def test_invalid_token_dev_mode_false_returns_401(self):
        """Invalid token + DEV_MODE=false → 401 Unauthorized."""
        from app.core.security import get_current_user
        from app.config import settings

        with patch.object(settings, 'DEV_MODE', False):
            mock_request = MagicMock()
            mock_request.headers = {"Authorization": "Bearer invalid_token_here"}

            with pytest.raises(HTTPException) as exc_info:
                get_current_user(request=mock_request)

            assert exc_info.value.status_code == 401
            assert "Invalid" in exc_info.value.detail or "token" in exc_info.value.detail.lower()

    def test_no_token_dev_mode_creates_user_if_not_exists(self):
        """DEV_MODE + no user in DB → creates user id=1."""
        from app.core.security import get_current_user, _get_dev_mode_user
        from app.config import settings

        with patch.object(settings, 'DEV_MODE', True):
            mock_db = MagicMock()
            mock_query = MagicMock()
            mock_query.filter.return_value.first.return_value = None  # User doesn't exist
            mock_db.query.return_value = mock_query

            with patch('app.core.security._get_db_session', return_value=mock_db):
                mock_request = MagicMock()
                mock_request.headers = {}

                user = get_current_user(request=mock_request)

                # Should have called db.add() to create user
                assert mock_db.add.called
                assert mock_db.commit.called