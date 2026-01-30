from fastapi import APIRouter

router = APIRouter(prefix="/api/guides", tags=["guides"])


@router.get("/ping")
def guides_ping():
    return {"status": "ok", "message": "guides router alive"}
