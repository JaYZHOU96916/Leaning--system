from app.models import Course
from app.sync.courses import CourseSyncService
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select


class FakeCanvasClient:
    async def get_all(self, url: str, **_: object) -> list[dict[str, object]]:
        assert url == "/courses"
        return [
            {
                "id": 241266,
                "name": "Data Mining",
                "course_code": "COMP90049",
                "workflow_state": "available",
                "term": {"name": "Semester 2, 2026"},
                "start_at": "2026-07-27T00:00:00Z",
                "end_at": "2026-10-30T00:00:00Z",
                "html_url": "https://canvas.lms.unimelb.edu.au/courses/241266",
            }
        ]


async def test_course_sync_bootstraps_and_is_idempotent() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app.db import create_db_and_tables

    create_db_and_tables(engine)
    service = CourseSyncService(FakeCanvasClient())
    with Session(engine) as session:
        first = await service.sync_courses(session)
        second = await service.sync_courses(session)
        course = session.exec(select(Course)).one()

    assert first.created == 1
    assert second.unchanged == 1
    assert course.canvas_id == 241266
    assert course.term_name == "Semester 2, 2026"
