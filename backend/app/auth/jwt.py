# app/auth/jwt.py
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError

from app.core.config import settings
from app.core import AppError, ErrorCode, ErrorReason

def create_access_token(*, subject: str, expires_minutes: int | None = None) -> str:
    minutes = expires_minutes or settings.JWT_ACCESS_TOKEN_EXPIRES_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise AppError(
            code=ErrorCode.UNAUTHORIZED,
            reason=ErrorReason.AUTH_INVALID,
            message="Invalid or expired token",
        )
