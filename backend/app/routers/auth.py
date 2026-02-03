# app/routers/auth.py
from pydantic import BaseModel
from fastapi import APIRouter

from app.core.config import settings
from app.auth.jwt import create_access_token
from app.core import AppError, ErrorCode, ErrorReason

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int

@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest) -> LoginResponse:
    if req.username != settings.ADMIN_USERNAME or req.password != settings.ADMIN_PASSWORD:
        raise AppError(
            code=ErrorCode.UNAUTHORIZED,
            reason=ErrorReason.AUTH_INVALID,
            message="Invalid credentials",
        )

    token = create_access_token(subject=settings.ADMIN_USERNAME)
    return LoginResponse(
        access_token=token,
        expires_in_minutes=settings.JWT_ACCESS_TOKEN_EXPIRES_MINUTES,
    )
