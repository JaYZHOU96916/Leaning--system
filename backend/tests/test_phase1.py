from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.alerts.service import AlertMessage, dispatch_due_alerts
from app.calendar.feed import build_calendar_feed
from app.core.config import Settings
from app.db import create_db_and_tables, get_session
from app.main import create_app
from app.models import Assignment, Course, ScheduleEvent
from app.sync.assignments import determine_submission_status
from fastapi.testclient import TestClient
from icalendar import Calendar
from sqlmodel import Session, create_engine


class RecordingNotifier:
    channel = "test"

    def __init__(self) -> None:
        self.messages: list[AlertMessage] = []

    async def send(self, message: AlertMessage) -> None:
        self.messages.append(message)


def make_engine(tmp_path: Path):
    return create_engine(
        f"sqlite:///{tmp_path / 'phase1.db'}",
        connect_args={"check_same_thread": False},
    )


async def test_ddl_alerts_are_sent_once_per_level(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    create_db_and_tables(engine)
    now = datetime(2026, 9, 20, 10, tzinfo=UTC)
    with Session(engine) as session:
        course = Course(canvas_id=101, name="Distributed Systems")
        session.add(course)
        session.commit()
        session.refresh(course)
        session.add(
            Assignment(
                canvas_id=202,
                course_id=course.id,
                name="Project report",
                due_at=now + timedelta(hours=2),
                submission_status="unsubmitted",
            )
        )
        session.commit()
        notifier = RecordingNotifier()
        assert await dispatch_due_alerts(session, notifier, now=now) == 1
        assert await dispatch_due_alerts(session, notifier, now=now) == 0

    assert len(notifier.messages) == 1
    assert notifier.messages[0].alert_level == "3h"


def test_submission_status_classification() -> None:
    now = datetime(2026, 9, 20, 10, tzinfo=UTC)
    assert determine_submission_status({"id": 1}, now=now) == "unsubmitted"
    assert determine_submission_status(
        {"id": 1, "due_at": "2026-09-20T09:00:00Z"}, now=now
    ) == "overdue"
    assert determine_submission_status(
        {"id": 1, "submission": {"submitted_at": "2026-09-20T08:00:00Z"}}, now=now
    ) == "submitted"
    assert determine_submission_status({"id": 1, "submission": {"score": 85}}, now=now) == "graded"


def test_ics_feed_is_rfc5545_parseable_and_filterable(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    create_db_and_tables(engine)
    now = datetime(2026, 9, 20, 10, tzinfo=UTC)
    with Session(engine) as session:
        first = Course(canvas_id=1, name="Algorithms")
        second = Course(canvas_id=2, name="Networks")
        session.add(first)
        session.add(second)
        session.commit()
        session.refresh(first)
        session.refresh(second)
        session.add(
            Assignment(
                canvas_id=11,
                course_id=first.id,
                name="Midterm",
                due_at=now + timedelta(days=1),
            )
        )
        session.add(
            ScheduleEvent(
                canvas_id=12,
                course_id=second.id,
                title="Tutorial",
                start_at=now,
            )
        )
        session.commit()
        payload = build_calendar_feed(session, course_id=first.id, now=now)

    parsed = Calendar.from_ical(payload)
    events = [component for component in parsed.walk() if component.name == "VEVENT"]
    assert len(events) == 1
    assert events[0].get("SUMMARY") == "[DDL] Algorithms - Midterm"
    assert parsed.get("VERSION") == "2.0"


def test_calendar_http_endpoint_returns_ics(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    create_db_and_tables(engine)
    now = datetime(2026, 9, 20, 10, tzinfo=UTC)
    with Session(engine) as session:
        course = Course(canvas_id=31, name="Operating Systems")
        session.add(course)
        session.commit()
        session.refresh(course)
        course_id = course.id
        session.add(
            Assignment(
                canvas_id=32,
                course_id=course.id,
                name="Lab 1",
                due_at=now + timedelta(days=1),
            )
        )
        session.commit()

    app = create_app(Settings(environment="test"), engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        response = client.get(f"/api/calendar/feed.ics?course_id={course_id}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert b"Lab 1" in response.content
