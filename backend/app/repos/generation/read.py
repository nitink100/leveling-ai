

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.cell_generation import CellGeneration


class GenerationReadRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_cell_generation(self, *, cell_id, prompt_name: str, prompt_version: str) -> CellGeneration | None:
        return (
            self.db.query(CellGeneration)
            .filter(
                CellGeneration.cell_id == cell_id,
                CellGeneration.prompt_name == prompt_name,
                CellGeneration.prompt_version == prompt_version,
            )
            .first()
        )

    def count_success_for_guide(self, *, guide_id, prompt_name: str, prompt_version: str) -> int:
        return int(
            self.db.query(func.count(CellGeneration.id))
            .filter(
                CellGeneration.guide_id == guide_id,
                CellGeneration.prompt_name == prompt_name,
                CellGeneration.prompt_version == prompt_version,
                CellGeneration.status == "SUCCESS",
            )
            .scalar()
            or 0
        )

    def count_total_for_guide(self, *, guide_id, prompt_name: str, prompt_version: str) -> int:
        # total rows generated (success+failed), used for progress checks
        return int(
            self.db.query(func.count(CellGeneration.id))
            .filter(
                CellGeneration.guide_id == guide_id,
                CellGeneration.prompt_name == prompt_name,
                CellGeneration.prompt_version == prompt_version,
            )
            .scalar()
            or 0
        )

    def list_generations_for_guide(self, *, guide_id, prompt_name: str, prompt_version: str) -> list[CellGeneration]:
        """Return all generation rows for a guide for the given prompt+version."""
        return (
            self.db.query(CellGeneration)
            .filter(
                CellGeneration.guide_id == guide_id,
                CellGeneration.prompt_name == prompt_name,
                CellGeneration.prompt_version == prompt_version,
            )
            .all()
        )
