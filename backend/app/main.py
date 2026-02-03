from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers.health import router as health_router
from app.routers.guides import router as guides_router
from app.routers.root import router as root_router
from app.core.exception_handlers import app_error_handler, unhandled_exception_handler

from app.core import AppError, ErrorCode, ErrorReason

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.middleware.request_logging import RequestLoggingMiddleware
from app.routers.health import router as health_router
from app.routers.guides import router as guides_router
from app.routers.root import router as root_router
from app.core.exception_handlers import app_error_handler, unhandled_exception_handler
from app.core import AppError


configure_logging()

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(root_router)
app.include_router(health_router)
app.include_router(guides_router)

def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    # Allow local frontend dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(guides_router)
    app.include_router(root_router)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    return app

app = create_app()
