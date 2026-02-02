"""
guide_service.py
- Purpose: Orchestrates the "upload leveling guide" workflow end-to-end.
- Owns: validation, DB writes via repos, storage upload, status updates.
- Design: Thick service; routers remain thin and easy to reason about.
"""

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.schemas.guide import LevelingGuideCreateResponse
from app.validations.file_validators import validate_pdf_upload
from app.validations.guide_validators import validate_role_title, normalize_website_url
from app.constants.statuses import GuideStatus
from app.core import AppError, ErrorCode, ErrorReason
from app.repos.company.write import CompanyWriteRepo
from app.repos.leveling_guide.write import LevelingGuideWriteRepo
from app.repos.leveling_guide.read import LevelingGuideReadRepo
from app.services.storage.supabase_storage import SupabaseStorage, StoredObject


class GuideService:
    def __init__(self, db: Session, storage: SupabaseStorage):
        self.db = db
        self.storage = storage

        self.company_write = CompanyWriteRepo(db)
        self.guide_write = LevelingGuideWriteRepo(db)
        self.guide_read = LevelingGuideReadRepo(db)

    def create_guide_from_upload(self, website_url: str, role_title: str, pdf: UploadFile) -> LevelingGuideCreateResponse:
        """
        Phase-1 clean workflow (consistent DB row):
        1) Validate inputs
        2) Normalize URL and upsert Company
        3) Upload PDF to Supabase Storage (private bucket)
        4) Create LevelingGuide row in DB in QUEUED with pdf_path already set
        5) Return UI-friendly response

        Why upload-before-create?
        - In Phase-1, pdf_path should be non-null and correct at creation time.
        - Worker can safely assume any QUEUED guide has a valid pdf_path.
        """
        validate_role_title(role_title)
        normalized_url = normalize_website_url(website_url)
        validate_pdf_upload(pdf)

        company = self.company_write.upsert_by_website(normalized_url)

        # Upload first so we can persist a consistent guide row with a valid pdf_path.
        stored: StoredObject = self.storage.upload_private_pdf(company_id=company.id, file=pdf)

        guide = self.guide_write.create_guide(
            company_id=company.id,
            role_title=role_title.strip() if role_title else None,
            status=GuideStatus.QUEUED,
            pdf_path=stored.path,
            original_filename=pdf.filename,
            mime_type=pdf.content_type,
        )

        return LevelingGuideCreateResponse.from_guide(guide)

    def get_status(self, guide_id):
        guide = self.guide_read.get_by_id(guide_id)
        return guide

    def get_signed_pdf_url(self, guide_id) -> str:
        guide = self.guide_read.get_by_id(guide_id)
        if not guide or not guide.pdf_path:
            raise AppError(
                code=ErrorCode.NOT_FOUND,
                reason=ErrorReason.MISSING_RESOURCE,
                message="PDF not available for this guide yet",
                http_status=404,
            )

        obj = StoredObject(bucket=self.storage._bucket, path=guide.pdf_path)
        return self.storage.create_signed_download_url(obj)
