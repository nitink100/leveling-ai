"""
guide_cell.py
- Purpose: Each (competency, level) grid cell definition + link to generations.
"""

import uuid
from datetime import datetime
from sqlalchemy import Text, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base
from app.models.company import utcnow


class GuideCell(Base):
    __tablename__ = "guide_cells"
    __table_args__ = (
        UniqueConstraint("competency_id", "level_id", name="uq_cells_competency_level"),
        Index("ix_cells_guide", "guide_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guide_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leveling_guides.id"), nullable=False)

    competency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("competencies.id"), nullable=False)
    level_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("levels.id"), nullable=False)

    definition_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_artifact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("guide_artifacts.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)

    guide: Mapped["LevelingGuide"] = relationship(back_populates="cells")
    competency: Mapped["Competency"] = relationship(back_populates="cells")
    level: Mapped["Level"] = relationship(back_populates="cells")

    generations: Mapped[list["CellGeneration"]] = relationship(
        back_populates="cell",
        cascade="all, delete-orphan",
        order_by="CellGeneration.created_at",
    )
