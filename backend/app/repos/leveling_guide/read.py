"""
leveling_guide/read.py
- Purpose: Read-side DB operations for LevelingGuide.
- Design: Keeps query access patterns centralized.
"""

from sqlalchemy.orm import Session
from app.models.leveling_guide import LevelingGuide
from app.models.guide_artifact import GuideArtifact

class LevelingGuideReadRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, guide_id):
        return self.db.query(LevelingGuide).filter(LevelingGuide.id == guide_id).first()

    def list_by_company(self, company_id, limit: int = 50):
        return (
            self.db.query(LevelingGuide)
            .filter(LevelingGuide.company_id == company_id)
            .order_by(LevelingGuide.created_at.desc())
            .limit(limit)
            .all()
        )
    
    def list_by_status(self, status: str, limit: int = 50):
        return (
            self.db.query(LevelingGuide)
            .filter(LevelingGuide.status == status)
            .order_by(LevelingGuide.created_at.asc())
            .limit(limit)
            .all()
        )

    def get_artifact(self, guide_id: str, type: str) -> GuideArtifact | None:
        return (
            self.db.query(GuideArtifact)
            .filter(GuideArtifact.guide_id == guide_id, GuideArtifact.type == type)
            .order_by(GuideArtifact.created_at.desc())
            .first()
        )

