"""
leveling_guide.py
- Purpose: Stores leveling guide upload metadata + processing status.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base
from app.models.company import utcnow


class LevelingGuide(Base):
    __tablename__ = "leveling_guides"
    
    __table_args__ = (
        # Fast filtering by company
        Index("ix_leveling_guides_company_id", "company_id"),
        # Worker polling: find oldest QUEUED first
        Index("ix_leveling_guides_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    role_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    company: Mapped["Company"] = relationship(back_populates="guides")

    artifacts: Mapped[list["GuideArtifact"]] = relationship(
        back_populates="guide",
        cascade="all, delete-orphan",
    )
    parse_runs: Mapped[list["ParseRun"]] = relationship(
        back_populates="guide",
        cascade="all, delete-orphan",
    )

    levels: Mapped[list["Level"]] = relationship(
        back_populates="guide",
        cascade="all, delete-orphan",
        order_by="Level.position",
    )
    competencies: Mapped[list["Competency"]] = relationship(
        back_populates="guide",
        cascade="all, delete-orphan",
        order_by="Competency.position",
    )
    cells: Mapped[list["GuideCell"]] = relationship(
        back_populates="guide",
        cascade="all, delete-orphan",
    )
