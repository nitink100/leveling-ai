# app/repos/matrix/write.py


from sqlalchemy.orm import Session

from app.models.level import Level
from app.models.competency import Competency
from app.models.guide_cell import GuideCell


class MatrixWriteRepo:
    def __init__(self, db: Session):
        self.db = db

    # -------- Levels (columns) --------
    def upsert_level(self, guide_id, code: str, position: int, title: str | None = None) -> Level:
        row = (
            self.db.query(Level)
            .filter(Level.guide_id == guide_id, Level.code == code)
            .first()
        )
        if row:
            row.position = position
            if title is not None:
                row.title = title
            self.db.flush()
            self.db.refresh(row)
            return row

        row = Level(
            guide_id=guide_id,
            code=code,
            title=title,
            position=position,
        )
        self.db.add(row)
        self.db.flush()
        self.db.refresh(row)
        return row

    # -------- Competencies (rows) --------
    def upsert_competency(self, guide_id, name: str, position: int) -> Competency:
        row = (
            self.db.query(Competency)
            .filter(Competency.guide_id == guide_id, Competency.name == name)
            .first()
        )
        if row:
            row.position = position
            self.db.flush()
            self.db.refresh(row)
            return row

        row = Competency(
            guide_id=guide_id,
            name=name,
            position=position,
        )
        self.db.add(row)
        self.db.flush()
        self.db.refresh(row)
        return row

    # -------- Cells --------
    # NOTE: unique constraint is (competency_id, level_id) so guide_id is redundant for lookup
    def upsert_cell(
        self,
        guide_id,
        competency_id,
        level_id,
        definition_text: str | None,
        *,
        source_artifact_id=None,
    ) -> GuideCell:
        row = (
            self.db.query(GuideCell)
            .filter(
                GuideCell.competency_id == competency_id,
                GuideCell.level_id == level_id,
            )
            .first()
        )
        if row:
            row.definition_text = definition_text
            # set source only if provided (don’t overwrite existing with None)
            if source_artifact_id is not None:
                row.source_artifact_id = source_artifact_id
            self.db.flush()
            self.db.refresh(row)
            return row

        row = GuideCell(
            guide_id=guide_id,
            competency_id=competency_id,
            level_id=level_id,
            definition_text=definition_text,
            source_artifact_id=source_artifact_id,
        )
        self.db.add(row)
        self.db.flush()
        self.db.refresh(row)
        return row
