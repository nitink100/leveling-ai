"""
level.py
- Purpose: One level column in the grid (L1, L2, Senior...).
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base
from app.models.company import utcnow


class Level(Base):
    __tablename__ = "levels"
    __table_args__ = (
        UniqueConstraint("guide_id", "code", name="uq_levels_guide_code"),
        Index("ix_levels_guide_position", "guide_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guide_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leveling_guides.id"), nullable=False)

    code: Mapped[str] = mapped_column(String(64), nullable=False)   # L1, L2, Senior...
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)

    guide: Mapped["LevelingGuide"] = relationship(back_populates="levels")
    cells: Mapped[list["GuideCell"]] = relationship(back_populates="level")
