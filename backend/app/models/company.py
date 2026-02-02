"""
company.py
- Purpose: Company owning leveling guides.
"""

import uuid
from datetime import datetime
from sqlalchemy import Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.models.base import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    website_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)

    guides: Mapped[list["LevelingGuide"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
