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
    svc: GuideService = Depends(get_guide_service),
):
    return svc.create_guide_from_upload(website_url=website_url, role_title=role_title, pdf=pdf)


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
