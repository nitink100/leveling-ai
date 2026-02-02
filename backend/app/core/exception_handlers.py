"""
exception_handlers.py
- Purpose: Convert AppError (and generic exceptions) into consistent API responses.
"""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core import AppError, ErrorCode, ErrorReason



async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    # In production: log exc with stacktrace
    return JSONResponse(
        status_code=500,
        content={"error": {"code": ErrorCode.INTERNAL_ERROR, "reason": "Unhandled exception"}},
    )
