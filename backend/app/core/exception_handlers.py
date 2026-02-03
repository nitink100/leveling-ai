"""
exception_handlers.py
- Purpose: Convert AppError (and generic exceptions) into consistent API responses.

Also logs errors with request context so failures are diagnosable.
"""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core import AppError, ErrorCode

logger = logging.getLogger("app.exceptions")


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "app_error",
        extra={
            "path": str(getattr(request.url, "path", "")),
            "method": request.method,
            "status_code": exc.status_code,
            "code": getattr(exc, "code", None),
            "reason": getattr(exc, "reason", None),
        },
    )
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        extra={"path": str(getattr(request.url, "path", "")), "method": request.method},
    )
    return JSONResponse(
        status_code=500,
        content={"error": {"code": ErrorCode.INTERNAL_ERROR, "reason": "Unhandled exception"}},
    )
