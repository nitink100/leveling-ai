"""
cell_generation.py
- Purpose: Stores LLM outputs for each cell (3 examples) plus metadata.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base
from app.models.company import utcnow


class CellGeneration(Base):
    __tablename__ = "cell_generations"
    __table_args__ = (
        Index("ix_generations_cell_created", "cell_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cell_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("guide_cells.id"), nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")  # PENDING, SUCCESS, FAILED
    examples_json: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)

    cell: Mapped["GuideCell"] = relationship(back_populates="generations")
