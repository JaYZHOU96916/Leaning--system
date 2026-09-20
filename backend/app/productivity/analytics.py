from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app.models import Course, FocusSession
from app.productivity.focus import as_utc, elapsed_seconds


def focus_analytics(
    session: Session,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    now = now or datetime.now(UTC)
    end = end or now
    start = start or (end - timedelta(days=7))
    sessions = session.exec(
        select(FocusSession).where(FocusSession.started_at < end)
    ).all()
    courses = {course.id: course.name for course in session.exec(select(Course)).all()}
    by_course: defaultdict[str, int] = defaultdict(int)
    by_day: defaultdict[str, int] = defaultdict(int)
    total = 0
    for focus in sessions:
        session_end = focus.ended_at or end
        if as_utc(session_end) <= as_utc(start) or as_utc(focus.started_at) >= as_utc(end):
            continue
        seconds = focus.duration_seconds
        if focus.status == "running" and focus.active_started_at is not None:
            seconds += elapsed_seconds(focus.active_started_at, now)
        seconds = max(0, seconds)
        total += seconds
        course_name = courses.get(focus.course_id, "未归类")
        by_course[course_name] += seconds
        day = as_utc(focus.started_at).date().isoformat()
        by_day[day] += seconds
    return {
        "start": as_utc(start).isoformat(),
        "end": as_utc(end).isoformat(),
        "total_seconds": total,
        "by_course": [
            {"course": key, "seconds": value} for key, value in sorted(by_course.items())
        ],
        "daily": [{"date": key, "seconds": value} for key, value in sorted(by_day.items())],
    }
