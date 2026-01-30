import uuid
from datetime import datetime
from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    Integer,
    Float,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base


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


class LevelingGuide(Base):
    __tablename__ = "leveling_guides"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    role_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="UPLOADED")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)

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


class Level(Base):
    __tablename__ = "levels"
    __table_args__ = (
        UniqueConstraint("guide_id", "code", name="uq_levels_guide_code"),
        Index("ix_levels_guide_position", "guide_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guide_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leveling_guides.id"), nullable=False)

    code: Mapped[str] = mapped_column(String(32), nullable=False)   # L1, L2, Senior...
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utcnow, nullable=False)

    guide: Mapped["LevelingGuide"] = relationship(back_populates="levels")
    cells: Mapped[list["GuideCell"]] = relationship(back_populates="level")


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
