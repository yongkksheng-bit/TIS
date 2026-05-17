"""Database seed script for demo user."""
import logging
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.models.user import User

logger = logging.getLogger(__name__)


def seed_demo_user():
    """Create demo user matching frontend authStore hardcoded user."""
    # Get a db session using the same pattern as FastAPI dependency
    db_gen = get_db()
    db = next(db_gen)
    try:
        existing = db.query(User).filter(User.id == 1).first()
        if existing:
            logger.info(f"Demo user already exists: id={existing.id}, username={existing.username}")
            return

        user = User(
            id=1,
            username="specialist",
            email="specialist@tis.local"
        )
        db.add(user)
        db.commit()
        logger.info("Demo user 'specialist' (id=1) created successfully")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create demo user: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_demo_user()