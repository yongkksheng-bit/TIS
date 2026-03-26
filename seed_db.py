"""Seed the local SQLite database with initial test data."""
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.user import User
from app.models.project import Project
from app.models.pricing import CostEstimate, PricingDecision
from datetime import datetime, timezone

DATABASE_URL = "sqlite:///./tis_test.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed():
    # Create only the tables we need (avoid PostgreSQL-specific JSONB columns)
    Base.metadata.create_all(bind=engine, tables=[
        Base.metadata.tables['users'],
        Base.metadata.tables['projects'],
        Base.metadata.tables['cost_estimates'],
        Base.metadata.tables['pricing_decisions'],
    ])
    db = SessionLocal()

    try:
        # Check if data already exists
        existing_users = db.query(User).count()
        if existing_users > 0:
            print(f"Database already has {existing_users} users. Skipping seed.")
            return

        # Create users
        boss = User(username="boss_zhang", email="boss@tis.com")
        specialist = User(username="specialist_li", email="li@tis.com")
        finance = User(username="finance_wang", email="wang@tis.com")
        db.add_all([boss, specialist, finance])
        db.commit()
        print(f"Created users: boss_zhang, specialist_li, finance_wang")

        # Create a test project
        project = Project(
            project_name="深圳市XX学校2026年食堂配送项目",
            project_type="service",
            owner_unit="深圳市XX学校",
            region="华南",
            budget_amount=1500000,
            status="evaluation_ready",
            relationship_flag=False,
            generation_mode="auto",
            bid_open_date=datetime(2026, 4, 15, 9, 0, 0, tzinfo=timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(project)
        db.commit()
        print(f"Created project: {project.project_name} (id={project.id})")

        # Create a cost estimate
        cost = CostEstimate(
            project_id=project.id,
            food_cost=600000,
            labor_cost=300000,
            logistics_cost=150000,
            management_cost=100000,
            other_cost=50000,
            total_cost=1200000,
            estimated_by=2,
        )
        db.add(cost)
        db.commit()
        print(f"Created cost estimate for project {project.id}")

        # Create a pricing decision
        pricing = PricingDecision(
            project_id=project.id,
            status="decided",
            cost_base=1200000,
            system_suggested_low=1260000,
            system_suggested_high=1380000,
            boss_final_price=1420000,
            budget_limit=1500000,
        )
        db.add(pricing)
        db.commit()
        print(f"Created pricing decision for project {project.id}")

        print("\nSeed completed successfully!")
        print(f"   Boss login: boss_zhang / any password")
        print(f"   Specialist login: specialist_li / any password")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
