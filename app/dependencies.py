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


# Current user dependency (placeholder for auth)
def get_current_user() -> Optional[dict]:
    """
    Dependency that returns the current authenticated user.

    Returns None if not authenticated.
    Actual implementation will decode JWT token from Authorization header.

    Usage:
        @app.get("/me")
        def get_me(current_user: dict = Depends(get_current_user)):
            ...
    """
    # Placeholder - actual implementation will parse JWT
    return None
