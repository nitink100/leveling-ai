# app/auth/deps.py
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt import decode_access_token
from app.core.config import settings
from app.core import AppError, ErrorCode, ErrorReason

bearer = HTTPBearer(auto_error=False)

def require_admin_token(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if not creds or creds.scheme.lower() != "bearer" or not creds.credentials:
        raise AppError(
            code=ErrorCode.UNAUTHORIZED,
            reason=ErrorReason.AUTH_REQUIRED,
            message="Missing Authorization: Bearer token",
        )

    payload = decode_access_token(creds.credentials)

    # Single-admin check
    sub = payload.get("sub")
    if sub != settings.ADMIN_USERNAME:
        raise AppError(
            code=ErrorCode.FORBIDDEN,
            reason=ErrorReason.AUTH_FORBIDDEN,
            message="Not authorized",
        )

    return payload
