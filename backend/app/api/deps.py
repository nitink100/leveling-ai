from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.guide_service import GuideService
from app.services.storage.supabase_storage import SupabaseStorage

def get_db() -> Generator[Session, None, None]:
    """
    Yields a DB session per request.
    Ensures the session is closed even on exceptions.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_storage() -> SupabaseStorage:
    """
    Provides the storage client. 
    Using Depends(get_storage) allows for easy mocking of S3/Supabase in tests.
    """
    return SupabaseStorage()


def get_guide_service(
    db: Session = Depends(get_db), 
    storage: SupabaseStorage = Depends(get_storage)
) -> GuideService:
    """
    Service dependency for guide flows.
    Injects both the DB session and the storage provider.
    """
    return GuideService(db=db, storage=storage)