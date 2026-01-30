from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.deps.db import get_db

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/db/health")
def db_health(db: Session = Depends(get_db)):
    db.execute(text("select 1"))
    return {"status": "ok", "db": "connected"}
