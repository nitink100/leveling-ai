"""
guide_artifact.py
- Purpose: Stores extracted text/chunks/JSON artifacts used across parsing & generation.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base
from app.models.company import utcnow


class GuideArtifact(Base):
    __tablename__ = "guide_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guide_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leveling_guides.id"), nullable=False)

    # PDF_TEXT, PAGE_TEXT, CHUNKS, PARSED_JSON, COMPANY_CONTEXT, etc.
    type: Mapped[str] = mapped_column(String(64), nullable=False)

    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)

    guide: Mapped["LevelingGuide"] = relationship(back_populates="artifacts")
