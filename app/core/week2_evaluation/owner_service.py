"""Owner Profile Service - Week 2 Evaluation.

Looks up owner history and returns a profile (or neutral default for new owners).
"""
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.owner import OwnerProfile
from app.models.enums import RelationshipLevel
from app.schemas.week2 import OwnerProfileResult


class OwnerProfileService:
    """Service for retrieving owner profiles with fallback to neutral defaults."""

    def __init__(self, db: Session):
        self.db = db

    def get_profile(self, owner_name: str, region: str) -> OwnerProfileResult:
        """
        Look up owner profile by (owner_name, region).

        If found, return the profile including relationship_level, cooperation_count,
        and preferred_styles. If not found, return a neutral default profile with
        is_new_owner=True.
        """
        profile = self.db.execute(
            select(OwnerProfile).where(
                OwnerProfile.owner_name == owner_name,
                OwnerProfile.region == region
            )
        ).scalar_one_or_none()

        if profile is None:
            return OwnerProfileResult(
                owner_name=owner_name,
                region=region,
                relationship_level=RelationshipLevel.NONE,
                cooperation_count=0,
                preferred_styles=None,
                is_new_owner=True,
            )

        return OwnerProfileResult(
            owner_name=profile.owner_name,
            region=profile.region,
            relationship_level=profile.relationship_level,
            cooperation_count=profile.cooperation_count,
            preferred_styles=profile.preferred_styles,
            is_new_owner=False,
        )
