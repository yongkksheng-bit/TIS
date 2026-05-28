"""Authentication endpoints - B.2 JWT Middleware."""
import logging
from fastapi import APIRouter, Depends, Request

from app.core.security import get_current_user, create_access_token, User
from app.schemas.common import ResponseWrapper

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

logger = logging.getLogger(__name__)


@router.get("/me")
def get_me(request: Request, current_user: User = Depends(get_current_user)):
    """Get current user info.

    Returns the authenticated user based on:
    - DEV_MODE=true + no token → user id=1 from DB
    - Valid JWT token → actual user from token
    - Invalid/missing token + DEV_MODE=false → 401

    Args:
        request: FastAPI request
        current_user: Injected user from get_current_user dependency

    Returns:
        ResponseWrapper with user data
    """
    logger.info(f"get_me called, user: {current_user.username if current_user else 'anonymous'}")
    return ResponseWrapper(
        code=200,
        message="success",
        data={
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email or ""
        }
    )


@router.post("/token")
def create_token(username: str, email: str = None):
    """Create a JWT token for testing (development only).

    DEV_MODE must be enabled to use this endpoint.

    Args:
        username: User's username
        email: User's email (optional)

    Returns:
        ResponseWrapper with JWT token
    """
    from app.config import settings

    if not settings.DEV_MODE:
        return ResponseWrapper(
            code=403,
            message="Token creation disabled in production",
            data=None
        )

    # Create demo user in database or get existing
    from app.dependencies import get_db
    from app.models.user import User as UserModel
    from sqlalchemy.orm import Session

    # Note: This is simplified for DEV_MODE. In production,
    # you would validate credentials properly.
    token = create_access_token(user_id=1, username=username, email=email)

    return ResponseWrapper(
        code=200,
        message="success",
        data={
            "access_token": token,
            "token_type": "bearer"
        }
    )