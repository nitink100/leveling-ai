"""
errors.py
- Purpose: AppError used across services/repos for consistent errors.
- Pattern: raise AppError(...) in service/repo, handler converts to JSON response.
"""



from dataclasses import dataclass
from typing import Any

from fastapi import status as http_status
from app.core.error_codes import ErrorCode
from app.core.error_reasons import ErrorReason
from app.core.error_codes import ErrorCode



@dataclass
class AppError(Exception):
    code: ErrorCode
    reason: str
    status_code: int = http_status.HTTP_400_BAD_REQUEST
    details: dict[str, Any] | None = None
    message: str | None = None  # Optional human-readable message

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": {
                "code": self.code,
                "reason": self.reason,
                "message": self.message if self.message else self.reason,
            }
        }
        if self.details:
            payload["error"]["details"] = self.details
        return payload


# Convenience constructors (optional but makes services cleaner)
def bad_request(reason: str = ErrorReason.INVALID_INPUT, *, code: ErrorCode = ErrorCode.VALIDATION_ERROR, details: dict | None = None) -> AppError:
    return AppError(code=code, reason=str(reason), status_code=http_status.HTTP_400_BAD_REQUEST, details=details)


def not_found(reason: str = ErrorReason.RESOURCE_NOT_FOUND, *, details: dict | None = None) -> AppError:
    return AppError(code=ErrorCode.NOT_FOUND, reason=str(reason), status_code=http_status.HTTP_404_NOT_FOUND, details=details)


def conflict(reason: str = ErrorReason.ALREADY_EXISTS, *, details: dict | None = None) -> AppError:
    return AppError(code=ErrorCode.CONFLICT, reason=str(reason), status_code=http_status.HTTP_409_CONFLICT, details=details)


def internal_error(reason: str = ErrorReason.UNKNOWN, *, details: dict | None = None) -> AppError:
    return AppError(code=ErrorCode.INTERNAL_ERROR, reason=str(reason), status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, details=details)
