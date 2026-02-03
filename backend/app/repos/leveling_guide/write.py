"""
leveling_guide/write.py
- Purpose: Write-side DB operations for LevelingGuide.
- Design: No business logic; persistence only.
"""

from sqlalchemy.orm import Session
from app.models.leveling_guide import LevelingGuide
from app.constants.statuses import GuideStatus
from app.models.guide_artifact import GuideArtifact
from app.models.parse_run import ParseRun



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
            status=status.value if hasattr(status, "value") else str(status),
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
    
    def update_status(self, guide_id, status: GuideStatus, error_message: str | None = None) -> LevelingGuide | None:
        guide = self.db.query(LevelingGuide).filter(LevelingGuide.id == guide_id).first()
        if not guide:
            return None
        guide.status = status.value if hasattr(status, "value") else str(status)
        if error_message is not None:
            guide.error_message = error_message
        self.db.flush()
        self.db.refresh(guide)
        return guide

    def create_parse_run(
        self,
        guide_id,
        strategy: str,
        status: str,
        confidence: float | None,
        model: str | None = None,
        prompt_version: str | None = None,
        input_artifact_id=None,
        output_artifact_id=None,
        error_message: str | None = None,
    ) -> ParseRun:
        run = ParseRun(
            guide_id=guide_id,
            strategy=strategy,
            status=status,
            confidence=confidence,
            model=model,
            prompt_version=prompt_version,
            input_artifact_id=input_artifact_id,
            output_artifact_id=output_artifact_id,
            error_message=error_message,
        )
        self.db.add(run)
        self.db.flush()
        self.db.refresh(run)
        return run

    def upsert_artifact(
        self,
        guide_id,
        type: str,
        *,
        content_text: str | None = None,
        content_json: dict | None = None,
    ) -> GuideArtifact:
        """Create a new artifact row, or update the latest one of the same type."""
        existing = (
            self.db.query(GuideArtifact)
            .filter(GuideArtifact.guide_id == guide_id, GuideArtifact.type == type)
            .order_by(GuideArtifact.created_at.desc())
            .first()
        )
        if existing:
            existing.content_text = content_text
            existing.content_json = content_json
            self.db.flush()
            self.db.refresh(existing)
            return existing

        artifact = GuideArtifact(guide_id=guide_id, type=type, content_text=content_text, content_json=content_json)
        self.db.add(artifact)
        self.db.flush()
        self.db.refresh(artifact)
        return artifact
    
    def claim_status(self, guide_id, *, from_status: str, to_status: str) -> bool:
        """
        Atomic status transition for distributed workers / idempotency.
        Returns True if claimed, False if not in expected from_status.
        """
        q = (
            self.db.query(LevelingGuide)
            .filter(LevelingGuide.id == guide_id, LevelingGuide.status == from_status)
        )
        updated = q.update({"status": to_status}, synchronize_session=False)
        # NOTE: do NOT commit here; service controls the transaction
        return updated == 1
