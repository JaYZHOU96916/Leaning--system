from collections.abc import Generator
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401  # Register tables before metadata operations.
from app.core.config import Settings, get_settings


def get_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    connect_args = (
        {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    )
    if settings.database_url.startswith("sqlite:///") and ":memory:" not in settings.database_url:
        db_path = settings.database_url.removeprefix("sqlite:///")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(settings.database_url, connect_args=connect_args, echo=False)


def create_db_and_tables(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session]:
    with Session(get_engine()) as session:
        yield session
