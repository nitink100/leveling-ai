"""
db/base.py
- Purpose: Provide Base + ensure models are imported for Alembic.
"""

from app.models.base import Base
import app.models  # noqa: F401  (ensures models are imported)

__all__ = ["Base"]
