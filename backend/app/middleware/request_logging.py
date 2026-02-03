from __future__ import annotations

import time
import uuid
import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.request_context import set_context, clear_context


logger = logging.getLogger("app.http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Accept upstream request id if present, else create one
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        set_context(request_id=rid)

        t0 = time.time()
        try:
            logger.info(
                "http.request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "query": str(request.url.query),
                },
            )
            response: Response = await call_next(request)
            dt_ms = int((time.time() - t0) * 1000)

            logger.info(
                "http.response",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": dt_ms,
                },
            )

            response.headers["x-request-id"] = rid
            return response
        finally:
            clear_context()
