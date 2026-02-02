"""
competency.py
- Purpose: One competency/row in the leveling grid.
"""

import uuid
from datetime import datetime
from sqlalchemy import Text, DateTime, ForeignKey, Integer, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base
from app.models.company import utcnow


class Competency(Base):
    __tablename__ = "competencies"
    __table_args__ = (
        UniqueConstraint("guide_id", "name", name="uq_competencies_guide_name"),
        Index("ix_competencies_guide_position", "guide_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guide_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leveling_guides.id"), nullable=False)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)

    guide: Mapped["LevelingGuide"] = relationship(back_populates="competencies")
    cells: Mapped[list["GuideCell"]] = relationship(back_populates="competency")
