from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, text

from app.api.calendar import router as calendar_router
from app.api.grades import router as grades_router
from app.api.materials import router as materials_router
from app.api.productivity import router as productivity_router
from app.api.sync import router as sync_router
from app.core.config import Settings
from app.db import create_db_and_tables, get_engine


def create_app(settings: Settings | None = None, engine: Any | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = engine or get_engine(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        create_db_and_tables(engine)
        yield

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(calendar_router)
    app.include_router(grades_router)
    app.include_router(materials_router)
    app.include_router(productivity_router)
    app.include_router(sync_router)

    @app.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        return {"status": "ok", "service": "academic-os"}

    return app


app = create_app()
