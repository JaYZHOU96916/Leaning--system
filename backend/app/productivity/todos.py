from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlmodel import Session, select

from app.models import Assignment, Course, ScheduleEvent, TodoItem


@dataclass(frozen=True)
class TodayTodo:
    key: str
    kind: str
    title: str
    course_id: int | None
    assignment_id: int | None
    due_at: datetime | None
    priority: int
    status: str
    source_id: int | None = None


def _day_bounds(day: date, *, tz_offset_hours: int = 0) -> tuple[datetime, datetime]:
    tz = UTC if tz_offset_hours == 0 else UTC
    start = datetime.combine(day, time.min, tzinfo=tz)
    return start, start + timedelta(days=1)


def aggregate_today(
    session: Session,
    *,
    today: date | None = None,
    now: datetime | None = None,
) -> list[TodayTodo]:
    now = now or datetime.now(UTC)
    today = today or now.date()
    day_start, day_end = _day_bounds(today)
    horizon = now + timedelta(hours=48)
    result: list[TodayTodo] = []

    assignment_rows = session.exec(
        select(Assignment, Course)
        .join(Course, Course.id == Assignment.course_id)
        .where(Assignment.due_at.is_not(None))
        .where(Assignment.due_at <= horizon)
        .where(Assignment.submission_status.in_(["unsubmitted", "overdue"]))
    ).all()
    for assignment, course in assignment_rows:
        assert assignment.due_at is not None
        comparison_now = now.replace(tzinfo=None) if assignment.due_at.tzinfo is None else now
        remaining = assignment.due_at - comparison_now
        urgent_priority = 1000 if remaining <= timedelta(hours=48) else 500
        if remaining <= timedelta(0):
            urgent_priority += 100
        result.append(
            TodayTodo(
                key=f"assignment:{assignment.id}",
                kind="deadline",
                title=f"{course.name} · {assignment.name}",
                course_id=course.id,
                assignment_id=assignment.id,
                due_at=assignment.due_at,
                priority=urgent_priority,
                status=assignment.submission_status,
                source_id=assignment.id,
            )
        )

    event_rows = session.exec(
        select(ScheduleEvent, Course)
        .join(Course, Course.id == ScheduleEvent.course_id, isouter=True)
        .where(ScheduleEvent.start_at >= day_start)
        .where(ScheduleEvent.start_at < day_end)
    ).all()
    for event, course in event_rows:
        result.append(
            TodayTodo(
                key=f"event:{event.id}",
                kind="schedule",
                title=f"{course.name if course else '课程'} · {event.title}",
                course_id=event.course_id,
                assignment_id=None,
                due_at=event.start_at,
                priority=800,
                status="scheduled",
                source_id=event.id,
            )
        )

    manual_rows = session.exec(
        select(TodoItem)
        .where(TodoItem.is_manual)
        .where(TodoItem.status != "completed")
        .where((TodoItem.due_at.is_(None)) | (TodoItem.due_at < day_end))
    ).all()
    for todo in manual_rows:
        result.append(
            TodayTodo(
                key=f"todo:{todo.id}",
                kind="manual",
                title=todo.title,
                course_id=todo.course_id,
                assignment_id=todo.assignment_id,
                due_at=todo.due_at,
                priority=todo.priority,
                status=todo.status,
                source_id=todo.id,
            )
        )
    return sorted(result, key=lambda item: (-item.priority, item.due_at or datetime.max))
