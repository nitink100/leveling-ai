from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers.health import router as health_router
from app.routers.guides import router as guides_router
from app.routers.root import router as root_router


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

    return app

app = create_app()
