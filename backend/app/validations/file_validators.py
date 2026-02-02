"""
file_validators.py
- Purpose: Centralized validation for file uploads (PDF constraints).
- Design: Raise AppError with stable error codes for UI + logs.
"""

from fastapi import UploadFile

from app.core import AppError, ErrorCode, ErrorReason
from app.core.error_codes import ErrorCode

MAX_BYTES = 10 * 1024 * 1024  # 10MB (prototype-safe)


def validate_pdf_upload(pdf: UploadFile) -> None:
    # Basic presence check
    if not pdf:
        raise AppError(code=ErrorCode.FILE_MISSING, status_code=422)

    # Content-type validation
    content_type = (pdf.content_type or "").lower()
    if content_type != "application/pdf":
        raise AppError(
            code=ErrorCode.FILE_NOT_PDF,
            status_code=422,
            details={"content_type": content_type},
        )

    # Note: size enforcement happens during streaming read in storage service
    # because UploadFile doesn't reliably expose size.
