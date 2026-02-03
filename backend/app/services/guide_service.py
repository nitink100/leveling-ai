# app/services/guide_service.py
"""
guide_service.py
- Purpose: Orchestrates the "upload leveling guide" workflow end-to-end.
- Owns: validation, DB writes via repos, storage upload, status updates.
- Design: Thick service; routers remain thin and easy to reason about.
"""


import uuid
import logging

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.schemas.guide import LevelingGuideCreateResponse
from app.validations.file_validators import validate_pdf_upload
from app.validations.guide_validators import validate_role_title, normalize_website_url
from app.constants.statuses import GuideStatus
from app.core import AppError, ErrorCode, ErrorReason
from app.core.config import settings

from app.repos.company.write import CompanyWriteRepo
from app.repos.leveling_guide.write import LevelingGuideWriteRepo
from app.repos.leveling_guide.read import LevelingGuideReadRepo

from app.services.storage.supabase_storage import SupabaseStorage, StoredObject

from app.pdf.extract import extract_text_from_bytes
from app.pdf.quality import score_extraction
from app.pdf.types import ExtractionResult

from app.schemas.matrix_schema import ParsedMatrix
from app.llm.client import llm_generate_structured
from app.repos.matrix.write import MatrixWriteRepo
from urllib.parse import urlparse
from app.tasks.guide_pipeline import extract_text_task

logger = logging.getLogger("app.guide_service")

class GuideService:
    def __init__(self, db: Session, storage: SupabaseStorage):
        self.db = db
        self.storage = storage

        self.company_write = CompanyWriteRepo(db)
        self.guide_write = LevelingGuideWriteRepo(db)
        self.guide_read = LevelingGuideReadRepo(db)

    def create_guide_from_upload(self, 
            website_url: str, 
            role_title: str, 
            pdf: UploadFile,
            *,
            company_name: str | None = None,
            company_context: str | None = None,
        ) -> LevelingGuideCreateResponse:

        validate_role_title(role_title)
        normalized_url = normalize_website_url(website_url)
        validate_pdf_upload(pdf)

        company = self.company_write.upsert_by_website(
            normalized_url,
            company_name=company_name,
            company_context=company_context,
        )

        stored: StoredObject = self.storage.upload_private_pdf(company_id=company.id, file=pdf)

        guide = self.guide_write.create_guide(
            company_id=company.id,
            role_title=role_title.strip() if role_title else None,
            status=GuideStatus.QUEUED,
            pdf_path=stored.path,
            original_filename=pdf.filename,
            mime_type=pdf.content_type,
        )
       
        logger.info(
            "guide.enqueued_extract",
            extra={"guide_id": str(guide.id), "role_title": role_title, "website_url": normalized_url},
        )
        # Kick off async Phase-2: PDF text extraction
        extract_text_task.delay(str(guide.id))
        
        return LevelingGuideCreateResponse.from_guide(guide)

    def get_status(self, guide_id):
        guide = self.guide_read.get_by_id(guide_id)
        return guide

    def get_signed_pdf_url(self, guide_id) -> str:
        guide = self.guide_read.get_by_id(guide_id)
        if not guide or not guide.pdf_path:
            raise AppError(
                code=ErrorCode.NOT_FOUND, 
                reason=str(ErrorReason.RESOURCE_NOT_FOUND), 
                message="PDF not available for this guide yet", 
                status_code=404
            )


        obj = StoredObject(bucket=self.storage._bucket, path=guide.pdf_path)
        return self.storage.create_signed_download_url(obj)

    def extract_pdf_text(self, guide_id: str, *, trace_id: str | None = None) -> ExtractionResult:
        """Phase-2: PDF -> text -> confidence gate -> store artifacts."""
        guide = self.guide_read.get_by_id(guide_id)
        if not guide:
            raise AppError(
                code=ErrorCode.NOT_FOUND, 
                reason=str(ErrorReason.RESOURCE_NOT_FOUND), 
                message="Guide not found", 
                status_code=404
            )


        self.guide_write.update_status(guide.id, GuideStatus.EXTRACTING_TEXT)

        pdf_obj = StoredObject(bucket=self.storage._bucket, path=guide.pdf_path)
        pdf_bytes = self.storage.download_bytes(pdf_obj)

        extracted = extract_text_from_bytes(pdf_bytes)
        quality = score_extraction(extracted.text, extracted.page_count, extracted.pages_with_text)

        # Save next to PDF (correct even if folder UUID != guide_id)
        base_dir = guide.pdf_path.rsplit("/", 1)[0]
        text_path = f"{base_dir}/extracted.txt"
        text_obj = StoredObject(bucket=self.storage._bucket, path=text_path)

        # IMPORTANT: your SupabaseStorage.upload_text should use upsert=True
        self.storage.upload_text(text_obj, extracted.text)

        artifact = self.guide_write.upsert_artifact(
            guide.id,
            "PDF_TEXT",
            content_text=None,
            content_json={
                "bucket": text_obj.bucket,
                "path": text_obj.path,
                "strategy": extracted.strategy,
                "page_count": extracted.page_count,
                "pages_with_text": extracted.pages_with_text,
                "confidence": quality.confidence,
                "char_count": quality.char_count,
                "word_count": quality.word_count,
                "line_count": quality.line_count,
                "printable_ratio": quality.printable_ratio,
                "flags": {
                    "is_scanned_likely": quality.is_scanned_likely,
                    "is_garbled_likely": quality.is_garbled_likely,
                    "has_matrix_signals": quality.has_matrix_signals,
                    "has_table_signals": quality.has_table_signals,
                },
                "notes": quality.notes,
            },
        )

        run_status = "SUCCESS"
        next_status = GuideStatus.TEXT_EXTRACTED
        error_message = None

        if quality.is_scanned_likely or quality.confidence < 0.20:
            run_status = "FAILED"
            next_status = GuideStatus.FAILED_BAD_PDF
            error_message = "PDF looks scanned/empty (no embedded text)"

        self.guide_write.create_parse_run(
            guide_id=guide.id,
            strategy=f"EXTRACT_{extracted.strategy.upper()}",
            status=run_status,
            confidence=quality.confidence,
            model=None,
            prompt_version=trace_id or "v1",
            input_artifact_id=None,
            output_artifact_id=artifact.id,
            error_message=error_message,
        )

        self.guide_write.update_status(guide.id, next_status, error_message=error_message)
        self.db.commit()

        return ExtractionResult(extracted=extracted, quality=quality)

    def parse_matrix(self, guide_id: str, *, trace_id: str | None = None) -> ParsedMatrix:
        guide_uuid = uuid.UUID(guide_id)
        guide = self.guide_read.get_by_id(guide_uuid)
        if not guide:
            raise AppError(code=ErrorCode.NOT_FOUND, 
            reason=str(ErrorReason.RESOURCE_NOT_FOUND), 
            message="Guide not found", 
            status_code=404
        )


        # ✅ Idempotency should be status-based (not artifact-based)
        if guide.status == GuideStatus.MATRIX_PARSED.value:
            existing = self.guide_read.get_artifact(guide_uuid, "MATRIX_JSON")
            if existing and existing.content_json:
                return ParsedMatrix(**existing.content_json)

        if guide.status == GuideStatus.FAILED_BAD_PDF.value:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                reason=ErrorReason.INVALID_INPUT,
                message="Guide is marked as bad PDF; cannot parse matrix",
                status_code=400,
            )

        # ---------- Step 1: CLAIM (short transaction) ----------
        try:
            claimed = self.guide_write.claim_status(
                guide_uuid,
                from_status=GuideStatus.TEXT_EXTRACTED.value,
                to_status=GuideStatus.PARSING_MATRIX.value,
            )
            if not claimed:
                # someone else is processing or guide not ready
                # re-read and return if already done
                self.db.rollback()
                latest = self.guide_read.get_by_id(guide_uuid)
                if latest and latest.status == GuideStatus.MATRIX_PARSED.value:
                    existing = self.guide_read.get_artifact(guide_uuid, "MATRIX_JSON")
                    if existing and existing.content_json:
                        return ParsedMatrix(**existing.content_json)
                raise AppError(
                    code=ErrorCode.VALIDATION_ERROR,
                    reason=ErrorReason.INVALID_INPUT,
                    message=f"Guide not in TEXT_EXTRACTED state (current={latest.status if latest else 'unknown'})",
                    status_code=409,
                )

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # ---------- Step 2: FETCH INPUT (no DB transaction) ----------
        pdf_text_artifact = self.guide_read.get_artifact(guide_uuid, "PDF_TEXT")
        if not pdf_text_artifact or not pdf_text_artifact.content_json:
            raise AppError(
                code=ErrorCode.NOT_FOUND, 
                reason=str(ErrorReason.RESOURCE_NOT_FOUND), 
                message="Missing PDF_TEXT artifact; run extraction first", 
                status_code=404
            )


        bucket = pdf_text_artifact.content_json["bucket"]
        path = pdf_text_artifact.content_json["path"]
        extracted_text = self.storage.download_bytes(StoredObject(bucket=bucket, path=path)).decode("utf-8", errors="replace")

        # sanitize a bit to reduce invalid JSON risk
        extracted_text = self._sanitize_for_llm(extracted_text)


        # ---------- Step 3: LLM COMPUTE (no DB transaction) ----------
        prompt_version = "v1"
        try:
            parsed = llm_generate_structured(
                purpose="parse_matrix",
                prompt_name="parse_matrix",
                prompt_version=prompt_version,
                variables={"text": extracted_text},
                schema=ParsedMatrix,
            )
        except Exception as e:
            # Failure path: record failed parse_run + status FAILED_PARSE
            try:
                self.db.rollback()
                self.guide_write.create_parse_run(
                    guide_id=guide_uuid,
                    strategy="PARSE_MATRIX_LLM_V1",
                    status="FAILED",
                    confidence=0.0,
                    model=getattr(settings, "GEMINI_MODEL", None),
                    prompt_version=prompt_version,
                    input_artifact_id=pdf_text_artifact.id,
                    output_artifact_id=None,
                    error_message=str(e),
                )
                self.guide_write.update_status(guide_uuid, GuideStatus.FAILED_PARSE, error_message=str(e))
                self.db.commit()
            except Exception:
                self.db.rollback()
            raise

        # ---------- Step 4: PERSIST ATOMICALLY (single transaction) ----------
        try:
            # Upsert MATRIX_JSON artifact
            matrix_artifact = self.guide_write.upsert_artifact(
                guide_uuid,
                "MATRIX_JSON",
                content_text=None,
                content_json=parsed.model_dump(),
            )

            # Normalize to tables
            matrix_repo = MatrixWriteRepo(self.db)

            level_ids = {}
            for i, lvl in enumerate(parsed.levels):
                level = matrix_repo.upsert_level(guide_uuid, code=lvl, position=i)
                level_ids[lvl] = level.id

            comp_ids = {}
            for i, comp in enumerate(parsed.competencies):
                c = matrix_repo.upsert_competency(guide_uuid, name=comp.name, position=i)
                comp_ids[comp.name] = c.id

            for comp in parsed.competencies:
                comp_id = comp_ids.get(comp.name)
                if not comp_id:
                    continue
                for lvl, txt in (comp.cells or {}).items():
                    lvl_id = level_ids.get(lvl)
                    if not lvl_id:
                        continue
                    matrix_repo.upsert_cell(
                        guide_uuid,
                        competency_id=comp_id,
                        level_id=lvl_id,
                        definition_text=(txt or "").strip(),
                        source_artifact_id=pdf_text_artifact.id,
                    )

            # ParseRun SUCCESS
            self.guide_write.create_parse_run(
                guide_id=guide_uuid,
                strategy="PARSE_MATRIX_LLM_V1",
                status="SUCCESS",
                confidence=float(getattr(parsed, "confidence", 0.8) or 0.8),
                model=getattr(settings, "GEMINI_MODEL", None),
                prompt_version=prompt_version,
                input_artifact_id=pdf_text_artifact.id,
                output_artifact_id=matrix_artifact.id,
                error_message=None,
            )

            # Final status marker
            self.guide_write.update_status(guide_uuid, GuideStatus.MATRIX_PARSED, error_message=None)

            self.db.commit()
            return parsed

        except Exception as e:
            self.db.rollback()

            # record failure in a separate small transaction
            try:
                self.guide_write.create_parse_run(
                    guide_id=guide_uuid,
                    strategy="PARSE_MATRIX_LLM_V1",
                    status="FAILED",
                    confidence=float(getattr(parsed, "confidence", 0.0) or 0.0),
                    model=getattr(settings, "GEMINI_MODEL", None),
                    prompt_version=prompt_version,
                    input_artifact_id=pdf_text_artifact.id,
                    output_artifact_id=None,
                    error_message=f"Persist failed: {e}",
                )
                self.guide_write.update_status(guide_uuid, GuideStatus.FAILED_PARSE, error_message=str(e))
                self.db.commit()
            except Exception:
                self.db.rollback()

            raise
    
    def _sanitize_for_llm(self, s: str) -> str:
        # keep content but reduce JSON-breaking weirdness
        s = s.replace("\u0000", "")
        s = s.replace("\r\n", "\n")
        s = s.replace('"', "'")
        return s
    
    def _derive_company_name_from_url(self, website_url: str) -> str:
        host = urlparse(website_url).netloc.lower()
        host = host[4:] if host.startswith("www.") else host
        root = host.split(".")[0] if host else "Company"
        return root[:1].upper() + root[1:]


    def build_base_context(self, company, role_title: str | None) -> str:
        name = (company.name or "").strip() or self._derive_company_name_from_url(company.website_url)
        ctx = (getattr(company, "context", None) or "").strip()

        lines = [
            f"Company: {name}",
            f"Website: {company.website_url}",
        ]
        if role_title and role_title.strip():
            lines.append(f"Role: {role_title.strip()}")

        if ctx:
            lines.append(f"Notes: {ctx}")
        else:
            lines.append("Notes: (none provided)")

        return "\n".join(lines)


