"""
leveling_guide/write.py
- Purpose: Write-side DB operations for LevelingGuide.
- Design: No business logic; persistence only.
"""

from sqlalchemy.orm import Session
from app.models.leveling_guide import LevelingGuide
from app.constants.statuses import GuideStatus


class LevelingGuideWriteRepo:
    def __init__(self, db: Session):
        self.db = db

    def create_guide(
        self,
        company_id,
        role_title: str | None,
        status: GuideStatus,
        pdf_path: str,
        original_filename: str | None,
        mime_type: str | None,
    ) -> LevelingGuide:
        guide = LevelingGuide(
            company_id=company_id,
            role_title=role_title,
            status=status,
            pdf_path=pdf_path,
            original_filename=original_filename,
            mime_type=mime_type,
        )
        self.db.add(guide)
        self.db.commit()
        self.db.refresh(guide)
        return guide

    def attach_pdf_path(self, guide_id, pdf_path: str) -> None:
        """
        Backward-compatible helper (ideally unused after Phase-1).
        Keep it in case older service code still creates first and attaches later.
        """
        guide = self.db.query(LevelingGuide).filter(LevelingGuide.id == guide_id).first()
        if not guide:
            return
        guide.pdf_path = pdf_path
        self.db.commit()