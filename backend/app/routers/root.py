from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["Root"])

@router.get("/")
def root():
    return {"message": "Backend running", "docs": "/docs"}
