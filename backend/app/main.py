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

    app.add_middleware(RequestLoggingMiddleware)

    # ---- CORS (env-driven) ----
    # Recommended env var:
    # CORS_ALLOW_ORIGINS="http://localhost:3000,https://yourapp.vercel.app"
    allow_origins = _split_csv(getattr(settings, "CORS_ALLOW_ORIGINS", None))

    # Optional: allow all Vercel preview deployments
    # Set to "true" only if you want previews to work without manual allowlisting.
    allow_vercel_previews = bool(getattr(settings, "CORS_ALLOW_VERCEL_PREVIEWS", False))

    cors_kwargs = dict(
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if allow_vercel_previews:
        # Allows https://<anything>.vercel.app
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=r"^https:\/\/.*\.vercel\.app$",
            **cors_kwargs,
        )
    else:
        # If you use cookies/credentials, do NOT use "*"
        # If allow_origins is empty, default to localhost only.
        if not allow_origins:
            allow_origins = ["http://localhost:3000"]

        app.add_middleware(
            CORSMiddleware,
            allow_origins=allow_origins,
            **cors_kwargs,
        )

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
