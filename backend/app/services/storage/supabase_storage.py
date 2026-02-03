"""
supabase_storage.py
- Purpose: Storage adapter for Supabase Storage (private bucket).
- Owns: upload/download URL generation, object path conventions.
- Design: Treat as an infrastructure adapter; no business logic.
"""



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
                status_code=500,
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
                status_code=400,
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
                message=f"Failed to upload PDF to storage:{e}",
                status_code=500,
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
                status_code=500,
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
            status_code=500,
        )
    
    def download_bytes(self, obj: StoredObject, expires_in_seconds: int = 600) -> bytes:
        """Download a private object as bytes using a signed URL."""
        url = self.create_signed_download_url(obj, expires_in_seconds=expires_in_seconds)

        try:
            import httpx

            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp.content
        except Exception as e:
            raise AppError(
                code=ErrorCode.STORAGE_ERROR,
                reason=ErrorReason.DOWNLOAD_FAILED,
                message="Failed to download object from storage",
                status_code=500,
            ) from e

    def upload_text(self, obj: StoredObject, text: str, content_type: str = "text/plain") -> StoredObject:
        """Upload plain text to storage under the provided object path."""
        data = text.encode("utf-8")

        try:
            # Variant A (common): upload(path, file, file_options)
            # file_options is NOT headers; it can include content-type and upsert.
            self._client.storage.from_(obj.bucket).upload(
                path=obj.path,
                file=data,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            return obj

        except TypeError:
            # Variant B (older): upload(path, file, options_dict) but options are treated like headers.
            # In this case, you cannot upsert via headers. Use update() instead.
            try:
                # Try upload without upsert (first-time write)
                self._client.storage.from_(obj.bucket).upload(obj.path, data, {"content-type": content_type})
                return obj
            except Exception:
                # If it already exists, fall back to update
                try:
                    self._client.storage.from_(obj.bucket).update(
                        path=obj.path,
                        file=data,
                        file_options={"content-type": content_type},
                    )
                    return obj
                except Exception as e:
                    raise AppError(
                        code=ErrorCode.STORAGE_ERROR,
                        reason=ErrorReason.UPLOAD_FAILED,
                        message=f"Failed to upload text artifact to storage: {e}",
                        status_code=500,
                    ) from e

        except Exception as e:
            raise AppError(
                code=ErrorCode.STORAGE_ERROR,
                reason=ErrorReason.UPLOAD_FAILED,
                message=f"Failed to upload text artifact to storage: {e}",
                status_code=500,
            ) from e
