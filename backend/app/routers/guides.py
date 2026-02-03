"""
guides.py
- Purpose: API routes for uploading and interacting with leveling guides.
- Design: Keep router thin. Delegate business logic to services.
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, status, HTTPException
from fastapi.responses import RedirectResponse

from app.schemas.guide import LevelingGuideCreateResponse
from app.services.guide_service import GuideService
from app.api.deps import get_guide_service

router = APIRouter(prefix="/api/guides", tags=["Guides"])


@router.post("", response_model=LevelingGuideCreateResponse, status_code=status.HTTP_201_CREATED)
def upload_leveling_guide(
    website_url: str = Form(...),
    role_title: str = Form(...),
    pdf: UploadFile = File(...),
    company_name: str | None = Form(None),
    company_context: str | None = Form(None),
    svc: GuideService = Depends(get_guide_service),
):
    return svc.create_guide_from_upload(
        website_url=website_url, 
        role_title=role_title, 
        pdf=pdf,
        company_name=company_name,
        company_context=company_context,
        )


@router.get("/{guide_id}/status")
def get_guide_status(guide_id: str, svc: GuideService = Depends(get_guide_service)):
    guide = svc.get_status(guide_id)
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")

    return {
        "guide_id": str(guide.id),
        "status": str(guide.status),
        "created_at": guide.created_at,
        "updated_at": guide.updated_at,
    }


@router.get("/{guide_id}/pdf")
def get_guide_pdf(guide_id: str, svc: GuideService = Depends(get_guide_service)):
    try:
        signed = svc.get_signed_pdf_url(guide_id)
        return RedirectResponse(url=signed, status_code=302)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to generate PDF link")

@router.post("/{guide_id}/extract-text")
def extract_text_phase2(guide_id: str, svc: GuideService = Depends(get_guide_service)):
    """Dev-only: trigger Phase-2 extraction synchronously."""
    res = svc.extract_pdf_text(guide_id)
    return {
        "guide_id": guide_id,
        "strategy": res.extracted.strategy,
        "page_count": res.extracted.page_count,
        "pages_with_text": res.extracted.pages_with_text,
        "confidence": res.quality.confidence,
        "flags": {
            "is_scanned_likely": res.quality.is_scanned_likely,
            "is_garbled_likely": res.quality.is_garbled_likely,
            "has_matrix_signals": res.quality.has_matrix_signals,
            "has_table_signals": res.quality.has_table_signals,
        },
        "notes": res.quality.notes,
    }

@router.post("/{guide_id}/parse-matrix")
def parse_matrix_phase3(guide_id: str, svc: GuideService = Depends(get_guide_service)):
    parsed = svc.parse_matrix(guide_id)
    return {"guide_id": guide_id, "levels": parsed.levels, "competencies": parsed.competencies}

@router.post("/{guide_id}/generate-examples")
def generate_examples_phase4(guide_id: str):
    from app.tasks.guide_pipeline import generate_cells_task  # noqa
    from app.tasks.guide_pipeline import finalize_generation_task  # noqa
    from app.db.session import SessionLocal
    from app.services.generation_service import GenerationService

    # start_phase4 does enqueue of all chunks
    db = SessionLocal()
    try:
        svc = GenerationService(db=db)
        out = svc.start_phase4(guide_id)
        return out
    finally:
        db.close()

@router.get("/{guide_id}/results")
def get_guide_results(guide_id: str, prompt_version: str = "v1"):
    """Fetch the fully rendered matrix (definitions + generated examples)."""
    from app.db.session import SessionLocal
    from app.services.generation_service import GenerationService

    db = SessionLocal()
    try:
        svc = GenerationService(db=db)
        return svc.get_results(guide_id, prompt_version=prompt_version)
    finally:
        db.close()

