"""
supabase_storage.py
- Purpose: Storage adapter for Supabase Storage (private bucket).
- Owns: upload/download URL generation, object path conventions.
- Design: Treat as an infrastructure adapter; no business logic.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from fastapi import UploadFile

from app.core import AppError, ErrorCode, ErrorReason
from app.core.config import settings


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    path: str


class SupabaseStorage:
    """
    Minimal adapter around Supabase Storage.

    Assumptions:
    - Bucket is private
    - We generate signed URLs for downloads
    - Upload path is deterministic and does not depend on a DB guide_id
      (Phase-1: upload happens before DB guide row is created).
    """

    def __init__(self, bucket: str | None = None):
        self._bucket = bucket or settings.SUPABASE_STORAGE_BUCKET

        # Import lazily so missing dependency errors are localized.
        try:
            from supabase import create_client  # type: ignore
        except Exception as e:
            raise AppError(
                code=ErrorCode.CONFIG_ERROR,
                reason=ErrorReason.MISSING_DEPENDENCY,
                message="Supabase client library is not installed or failed to import",
                http_status=500,
            ) from e

        self._client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

    def _sanitize_filename(self, name: str | None) -> str:
        if not name:
            return "upload.pdf"
        # Simple sanitize: keep basename, drop any path parts
        base = os.path.basename(name)
        return base or "upload.pdf"

    def _build_private_pdf_path(self, company_id, filename: str | None) -> str:
        """
        Storage key convention:
        companies/{company_id}/guides/{uuid}/{filename}

        - No dependency on guide_id (Phase-1 requirement).
        - Unique enough to prevent collisions.
        """
        safe_name = self._sanitize_filename(filename)
        obj_id = uuid.uuid4()
        return f"companies/{company_id}/guides/{obj_id}/{safe_name}"

    def upload_private_pdf(self, company_id, file: UploadFile) -> StoredObject:
        """
        Upload the given UploadFile to the private bucket and return StoredObject.
        """
        path = self._build_private_pdf_path(company_id=company_id, filename=file.filename)

        try:
            content = file.file.read()
        except Exception as e:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                reason=ErrorReason.INVALID_INPUT,
                message="Failed to read uploaded PDF file",
                http_status=400,
            ) from e

        try:
            # Supabase python client: storage.from_(bucket).upload(path, file, file_options?)
            # We pass bytes; content-type is optional but nice to have.
            opts = {"content-type": file.content_type or "application/pdf"}
            res = self._client.storage.from_(self._bucket).upload(path, content, opts)
        except Exception as e:
            raise AppError(
                code=ErrorCode.STORAGE_ERROR,
                reason=ErrorReason.UPLOAD_FAILED,
                message="Failed to upload PDF to storage",
                http_status=500,
            ) from e

        # Some versions return dict-like, some return object; we just assume no exception == success.
        return StoredObject(bucket=self._bucket, path=path)

    def create_signed_download_url(self, obj: StoredObject, expires_in_seconds: int = 600) -> str:
        """
        Generate a signed download URL for a private object.
        """
        try:
            res = self._client.storage.from_(obj.bucket).create_signed_url(obj.path, expires_in_seconds)
        except Exception as e:
            raise AppError(
                code=ErrorCode.STORAGE_ERROR,
                reason=ErrorReason.SIGNED_URL_FAILED,
                message="Failed to create signed download URL",
                http_status=500,
            ) from e

        # Supabase returns a dict with signedURL in many client versions
        if isinstance(res, dict):
            url = res.get("signedURL") or res.get("signedUrl") or res.get("signed_url")
            if url:
                return url

        # Fallback: best-effort string cast
        if isinstance(res, str):
            return res

        raise AppError(
            code=ErrorCode.STORAGE_ERROR,
            reason=ErrorReason.SIGNED_URL_FAILED,
            message="Signed URL response was not in the expected format",
            http_status=500,
        )
