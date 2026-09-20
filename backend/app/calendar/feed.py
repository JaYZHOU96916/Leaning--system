from datetime import UTC, datetime, timedelta

from icalendar import Calendar, Event
from sqlmodel import Session, select

from app.models import Assignment, Course, ScheduleEvent


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def build_calendar_feed(
    session: Session,
    *,
    course_id: int | None = None,
    include_assignments: bool = True,
    include_events: bool = True,
    now: datetime | None = None,
) -> bytes:
    now = now or datetime.now(UTC)
    calendar = Calendar()
    calendar.add("prodid", "-//Canvas Academic OS//Academic Calendar//EN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")
    calendar.add("x-wr-calname", "Canvas Academic OS")
    calendar.add("x-wr-timezone", "UTC")

    courses = {
        course.id: course
        for course in session.exec(select(Course)).all()
        if course_id is None or course.id == course_id
    }
    if include_assignments:
        statement = select(Assignment).where(Assignment.due_at.is_not(None))
        if course_id is not None:
            statement = statement.where(Assignment.course_id == course_id)
        for assignment in session.exec(statement).all():
            assert assignment.due_at is not None
            course = courses.get(assignment.course_id)
            event = Event()
            event.add("uid", f"assignment-{assignment.canvas_id}@academic-os")
            event.add("dtstamp", now)
            event.add("dtstart", _as_utc(assignment.due_at))
            event.add("dtend", _as_utc(assignment.due_at) + timedelta(minutes=30))
            event.add("summary", f"[DDL] {course.name if course else 'Course'} - {assignment.name}")
            event.add("description", f"状态：{assignment.submission_status}")
            if assignment.html_url:
                event.add("url", assignment.html_url)
            event.add("categories", ["ACADEMIC-OS", "DEADLINE"])
            calendar.add_component(event)

    if include_events:
        statement = select(ScheduleEvent).where(ScheduleEvent.start_at.is_not(None))
        if course_id is not None:
            statement = statement.where(ScheduleEvent.course_id == course_id)
        for schedule_event in session.exec(statement).all():
            event = Event()
            event.add("uid", f"schedule-{schedule_event.canvas_id}@academic-os")
            event.add("dtstamp", now)
            event.add("dtstart", _as_utc(schedule_event.start_at))
            event.add(
                "dtend",
                _as_utc(schedule_event.end_at)
                if schedule_event.end_at
                else _as_utc(schedule_event.start_at) + timedelta(hours=1),
            )
            course = courses.get(schedule_event.course_id)
            event.add("summary", f"{course.name if course else '课程'} - {schedule_event.title}")
            if schedule_event.location:
                event.add("location", schedule_event.location)
            if schedule_event.html_url:
                event.add("url", schedule_event.html_url)
            event.add("categories", ["ACADEMIC-OS", "CLASS"])
            calendar.add_component(event)
    return calendar.to_ical()
