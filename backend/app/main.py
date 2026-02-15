# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.middleware.request_logging import RequestLoggingMiddleware
from app.routers.health import router as health_router
from app.routers.guides import router as guides_router
from app.routers.root import router as root_router
from app.routers.auth import router as auth_router
from app.core.exception_handlers import app_error_handler, unhandled_exception_handler
from app.core import AppError

configure_logging()


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def create_app() -> FastAPI:
    app = FastAPI(title=getattr(settings, "PROJECT_NAME", "API"))

    # 1. Define CORS logic first
    allow_origins = _split_csv(getattr(settings, "CORS_ALLOW_ORIGINS", None))
    if not allow_origins:
        allow_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

    cors_kwargs = dict(
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. ADD CORS MIDDLEWARE FIRST (so it is the last to wrap the app)
    app.add_middleware(CORSMiddleware, **cors_kwargs)

    # 3. ADD OTHER MIDDLEWARES AFTER
    app.add_middleware(RequestLoggingMiddleware)

    # Exception handlers
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Routers
    app.include_router(root_router)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(guides_router)

    return app


app = create_app()
