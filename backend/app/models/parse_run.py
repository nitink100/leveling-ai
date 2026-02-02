"""
parse_run.py
- Purpose: Tracks parsing attempts and LLM/heuristic strategy outcomes.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base
from app.models.company import utcnow


class ParseRun(Base):
    __tablename__ = "parse_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guide_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leveling_guides.id"), nullable=False)

    strategy: Mapped[str] = mapped_column(String(32), nullable=False)  # HEURISTIC, LLM_FALLBACK
    status: Mapped[str] = mapped_column(String(16), nullable=False)    # SUCCESS, FAILED
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    input_artifact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("guide_artifacts.id"), nullable=True)
    output_artifact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("guide_artifacts.id"), nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)

    guide: Mapped["LevelingGuide"] = relationship(back_populates="parse_runs")
