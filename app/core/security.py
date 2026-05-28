"""JWT Security module - B.2 JWT Middleware implementation."""
from fastapi import HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import jwt

from app.config import settings


class TokenPayload(BaseModel):
    """JWT token payload schema."""
    sub: str
    username: str
    email: Optional[str] = None
    exp: Optional[int] = None


class User(BaseModel):
    """User model for dependency injection."""
    id: int
    username: str
    email: Optional[str] = None


def _get_db_session():
    """Create a new DB session for dependency injection."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def get_current_user(request: Request) -> User:
    """Extract user from request.

    - DEV_MODE=true + no token → returns user id=1 from DB (or creates it)
    - Valid JWT token → returns user from token payload
    - Invalid/missing token + DEV_MODE=false → raises 401

    Args:
        request: FastAPI request object

    Returns:
        User: Current user (from DB or authenticated)

    Raises:
        HTTPException: 401 if token invalid and DEV_MODE=false
    """
    auth_header = request.headers.get("Authorization")

    # Case 1: No token provided
    if not auth_header:
        if settings.DEV_MODE:
            return _get_dev_mode_user()
        raise HTTPException(status_code=401, detail="Missing authorization token")

    # Case 2: Bearer token
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        if settings.DEV_MODE:
            return _get_dev_mode_user()
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    token = parts[1]

    # Case 3: Decode and validate JWT
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return User(
            id=int(payload["sub"]),
            username=payload["username"],
            email=payload.get("email")
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        if settings.DEV_MODE:
            return _get_dev_mode_user()
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


def _get_dev_mode_user() -> User:
    """Get or create the dev mode fallback user (id=1).

    In DEV_MODE, when no token is provided, we return the database user
    with id=1 to avoid FK constraint failures in subsequent operations.

    Returns:
        User: The dev mode user (id=1, username=specialist)
    """
    from app.models.user import User as UserModel

    db = _get_db_session()
    try:
        user = db.query(UserModel).filter(UserModel.id == 1).first()
        if not user:
            # Create user id=1 if it doesn't exist (matches seed data)
            user = UserModel(id=1, username="specialist", email="specialist@tis.local")
            db.add(user)
            db.commit()
            db.refresh(user)
        return User(id=user.id, username=user.username, email=user.email)
    finally:
        db.close()


def create_access_token(user_id: int, username: str, email: str = None) -> str:
    """Create a JWT access token for a user.

    Args:
        user_id: User's database ID
        username: User's username
        email: User's email (optional)

    Returns:
        str: Encoded JWT token
    """
    import time
    payload = {
        "sub": str(user_id),
        "username": username,
        "email": email,
        "exp": int(time.time()) + 86400  # 24 hours
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")