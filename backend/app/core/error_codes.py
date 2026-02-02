# app/core/error_codes.py
from enum import Enum

class ErrorCode(str, Enum):
    UNKNOWN = "UNKNOWN"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    DB_ERROR = "DB_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    # Upload / PDF
    FILE_MISSING = "FILE_MISSING"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"

    # Supabase / Storage
    STORAGE_UPLOAD_FAILED = "STORAGE_UPLOAD_FAILED"
