from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from sqlmodel import Session, text

from app.api.calendar import router as calendar_router
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
    app.include_router(calendar_router)
    app.include_router(sync_router)

    @app.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        return {"status": "ok", "service": "academic-os"}

    return app


app = create_app()
