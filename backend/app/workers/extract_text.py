"""app/workers/extract_text.py

Phase-2 worker entrypoint.
"""



import uuid
from sqlalchemy.orm import Session

from app.services.guide_service import GuideService
from app.services.storage.supabase_storage import SupabaseStorage


def run_extract_text(db: Session, guide_id: str, *, trace_id: str | None = None):
    if trace_id is None:
        trace_id = str(uuid.uuid4())

    svc = GuideService(db=db, storage=SupabaseStorage())
    return svc.extract_pdf_text(guide_id, trace_id=trace_id)
