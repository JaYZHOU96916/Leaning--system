from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from app.db import create_db_and_tables
from app.models import Assignment, Course, ScheduleEvent, TodoItem
from app.productivity.analytics import focus_analytics
from app.productivity.focus import FocusSessionService
from app.productivity.todos import aggregate_today
from sqlmodel import Session, create_engine


def make_engine(tmp_path: Path):
    return create_engine(
        f"sqlite:///{tmp_path / 'phase4.db'}",
        connect_args={"check_same_thread": False},
    )


def test_today_aggregation_prioritizes_deadlines_and_schedule(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    create_db_and_tables(engine)
    now = datetime(2026, 9, 20, 8, tzinfo=UTC)
    with Session(engine) as session:
        course = Course(canvas_id=701, name="Human Computer Interaction")
        session.add(course)
        session.commit()
        session.refresh(course)
        session.add(
            Assignment(
                canvas_id=702,
                course_id=course.id,
                name="Prototype",
                due_at=now + timedelta(hours=24),
                submission_status="unsubmitted",
            )
        )
        session.add(
            ScheduleEvent(
                canvas_id=703,
                course_id=course.id,
                title="Studio",
                start_at=now + timedelta(hours=2),
            )
        )
        session.add(TodoItem(title="Review notes", priority=20, is_manual=True))
        session.commit()
        items = aggregate_today(session, today=date(2026, 9, 20), now=now)

    assert [item.kind for item in items] == ["deadline", "schedule", "manual"]
    assert items[0].title.endswith("Prototype")


def test_focus_state_machine_accumulates_only_active_time(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    create_db_and_tables(engine)
    start = datetime(2026, 9, 20, 8, tzinfo=UTC)
    with Session(engine) as session:
        service = FocusSessionService(session)
        focus = service.start(now=start)
        with pytest.raises(ValueError, match="already active"):
            service.start(now=start + timedelta(minutes=1))
        focus = service.pause(focus, now=start + timedelta(minutes=25))
        assert focus.duration_seconds == 25 * 60
        focus = service.resume(focus, now=start + timedelta(minutes=40))
        focus = service.complete(focus, now=start + timedelta(minutes=55))
        assert focus.status == "completed"
        assert focus.duration_seconds == 40 * 60


def test_focus_analytics_groups_course_and_daily_trends(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    create_db_and_tables(engine)
    start = datetime(2026, 9, 20, 8, tzinfo=UTC)
    with Session(engine) as session:
        course = Course(canvas_id=801, name="Data Visualization")
        session.add(course)
        session.commit()
        session.refresh(course)
        service = FocusSessionService(session)
        focus = service.start(course_id=course.id, now=start)
        service.complete(focus, now=start + timedelta(minutes=50))
        stats = focus_analytics(
            session,
            start=start - timedelta(hours=1),
            end=start + timedelta(hours=1),
            now=start + timedelta(hours=1),
        )

    assert stats["total_seconds"] == 50 * 60
    assert stats["by_course"] == [{"course": "Data Visualization", "seconds": 50 * 60}]
    assert stats["daily"] == [{"date": "2026-09-20", "seconds": 50 * 60}]
