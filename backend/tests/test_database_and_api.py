from pathlib import Path

from app.core.config import Settings
from app.core.security import TokenCipher
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine


def test_database_initializes_all_phase_zero_tables() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app.db import create_db_and_tables

    create_db_and_tables(engine)
    table_names = set(SQLModel.metadata.tables)
    expected = {
        "course",
        "assignment",
        "assignment_group",
        "schedule_event",
        "material",
        "focus_session",
        "flashcard",
        "todo_item",
        "alert_delivery",
        "flashcard_job",
    }
    assert expected <= table_names


def test_health_endpoint_and_lifespan_create_database(tmp_path: Path) -> None:
    database_path = tmp_path / "academic_os.db"
    settings = Settings(database_url=f"sqlite:///{database_path}", environment="test")
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
    )
    app = create_app(settings, engine)

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "academic-os"}
    assert database_path.exists()


def test_canvas_token_is_hidden_and_can_be_encrypted() -> None:
    settings = Settings(canvas_api_token="super-secret-token")
    assert "super-secret-token" not in repr(settings)

    cipher = TokenCipher(TokenCipher.generate_key())
    encrypted = cipher.encrypt(settings.canvas_token_value)
    assert encrypted != settings.canvas_token_value
    assert cipher.decrypt(encrypted) == settings.canvas_token_value
