

from sqlalchemy.orm import Session

from app.models.cell_generation import CellGeneration


class GenerationWriteRepo:
    def __init__(self, db: Session):
        self.db = db

    def upsert_cell_generation(
        self,
        *,
        guide_id,
        cell_id,
        prompt_name: str,
        prompt_version: str,
        status: str,
        content_json: dict | None,
        model: str | None = None,
        trace_id: str | None = None,
        error_message: str | None = None,
    ) -> CellGeneration:
        existing = (
            self.db.query(CellGeneration)
            .filter(
                CellGeneration.cell_id == cell_id,
                CellGeneration.prompt_name == prompt_name,
                CellGeneration.prompt_version == prompt_version,
            )
            .first()
        )

        if existing:
            existing.status = status
            existing.content_json = content_json
            existing.model = model
            existing.trace_id = trace_id
            existing.error_message = error_message
            self.db.flush()
            self.db.refresh(existing)
            return existing

        row = CellGeneration(
            guide_id=guide_id,
            cell_id=cell_id,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            status=status,
            content_json=content_json,
            model=model,
            trace_id=trace_id,
            error_message=error_message,
        )
        self.db.add(row)
        self.db.flush()
        self.db.refresh(row)
        return row
