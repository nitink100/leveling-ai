"""
error_reasons.py
- Purpose: Human-friendly "reason" strings.
- Keep these stable; they may be surfaced in UI and emails.
"""

from enum import Enum


class ErrorReason(str, Enum):
    UNKNOWN = "Unknown error"

    INVALID_INPUT = "Invalid input"
    RESOURCE_NOT_FOUND = "Resource not found"
    ALREADY_EXISTS = "Resource already exists"
    NOT_AUTHENTICATED = "Not authenticated"
    NOT_AUTHORIZED = "Not authorized"
    TOO_MANY_REQUESTS = "Too many requests"

    DATABASE_UNAVAILABLE = "Database unavailable"
    STORAGE_UNAVAILABLE = "Storage unavailable"
    PDF_INVALID = "Invalid PDF"
    LLM_FAILED = "LLM request failed"
    UPLOAD_FAILED="upload failed"
    INTERNAL_ERROR= "Internal server error"
    MISSING_DEPENDENCY = "Missing dependency"
    AUTH_REQUIRED = "Authentication required"
    AUTH_INVALID = "Invalid authentication"
    AUTH_FORBIDDEN = "Authentication forbidden"