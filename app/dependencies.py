from typing import Generator, Optional
from sqlalchemy.orm import Session
import redis

from app.config import settings


# Database session dependency
def get_db() -> Generator[Session, None, None]:
    """
    Dependency that yields a SQLAlchemy database session.

    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            ...
    """
    # Placeholder - actual implementation will use SQLAlchemy engine
    # This will be wired up in Week 2 with actual DB connection
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Redis client dependency
def get_redis() -> redis.Redis:
    """
    Dependency that returns a Redis client.

    Usage:
        @app.get("/cache")
        def get_cache(redis_client: redis.Redis = Depends(get_redis)):
            ...
    """
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


# Re-export security.get_current_user so existing imports remain compatible
from app.core.security import get_current_user as _security_get_current_user, User
from fastapi import Request


def get_current_user(request: Request = None) -> User:
    """Dependency that returns the current authenticated user.

    For FastAPI Depends(): FastAPI auto-passes Request.
    For backward compat (direct calls without args): returns None.

    DEV_MODE fallback: returns user id=1 from DB (no token needed).
    """
    if request is None:
        # Backward compatibility for existing code that calls without args
        return None
    return _security_get_current_user(request)


__all__ = ["get_db", "get_redis", "get_current_user"]
