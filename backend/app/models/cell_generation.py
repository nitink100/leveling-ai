"""
cell_generation.py
- Purpose: Stores AI-generated examples for a single guide cell.
- One row per (cell_id, prompt_name, prompt_version) for idempotency + regeneration.
"""
import uuid
from datetime import datetime

from sqlalchemy import Text, DateTime, ForeignKey, UniqueConstraint, Index, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.company import utcnow


class CellGeneration(Base):
    __tablename__ = "cell_generations"
    __table_args__ = (
        UniqueConstraint("cell_id", "prompt_name", "prompt_version", name="uq_cellgen_cell_prompt_ver"),
        Index("ix_cellgen_guide", "guide_id"),
        Index("ix_cellgen_cell", "cell_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    guide_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leveling_guides.id"), nullable=False)
    cell_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("guide_cells.id"), nullable=False)

    prompt_name: Mapped[str] = mapped_column(String(64), nullable=False, default="generate_examples")
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="SUCCESS")  # SUCCESS | FAILED
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    content_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)

    # relationships
    cell: Mapped["GuideCell"] = relationship(back_populates="generations")
