from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["root"])

@router.get("/")
def root():
    return {"message": "Backend running", "docs": "/docs"}
