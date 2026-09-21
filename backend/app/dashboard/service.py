from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app.models import Assignment, Course, Flashcard, Material, ScheduleEvent

_COMPLETE_STATUSES = {"submitted", "graded"}


def _as_utc(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes even when Canvas supplied an offset."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _iso(value: datetime | None) -> str | None:
    normalised = _as_utc(value)
    return normalised.isoformat() if normalised else None


def _semester_progress(course: Course, now: datetime) -> int | None:
    start_at = _as_utc(course.start_at)
    end_at = _as_utc(course.end_at)
    if start_at is None or end_at is None or end_at <= start_at:
        return None
    elapsed = (now - start_at).total_seconds()
    total = (end_at - start_at).total_seconds()
    return round(max(0, min(1, elapsed / total)) * 100)


def build_overview(session: Session, *, now: datetime | None = None) -> dict[str, object]:
    """Build a small, UI-ready semester summary from the local Canvas mirror."""
    now = _as_utc(now or datetime.now(UTC))
    assert now is not None
    courses = session.exec(select(Course).order_by(Course.course_code, Course.name)).all()
    course_by_id = {course.id: course for course in courses if course.id is not None}

    course_rows: list[dict[str, object]] = []
    term_names: list[str] = []
    progress_values: list[int] = []
    for course in courses:
        assignments = session.exec(
            select(Assignment).where(Assignment.course_id == course.id).order_by(Assignment.due_at)
        ).all()
        completed = sum(item.submission_status in _COMPLETE_STATUSES for item in assignments)
        pending = [
            item
            for item in assignments
            if item.submission_status not in _COMPLETE_STATUSES
            and item.due_at is not None
            and _as_utc(item.due_at) >= now
        ]
        progress = _semester_progress(course, now)
        if progress is not None:
            progress_values.append(progress)
        if course.term_name:
            term_names.append(course.term_name)
        course_rows.append(
            {
                "id": course.id,
                "name": course.name,
                "course_code": course.course_code,
                "term_name": course.term_name,
                "assignment_total": len(assignments),
                "assignment_completed": completed,
                "semester_progress_percent": progress,
                "next_due_at": _iso(pending[0].due_at) if pending else None,
            }
        )

    open_assignments = session.exec(
        select(Assignment)
        .where(Assignment.due_at.is_not(None))
        .where(Assignment.submission_status.notin_(_COMPLETE_STATUSES))
        .order_by(Assignment.due_at)
    ).all()
    deadlines = [
        {
            "id": assignment.id,
            "course_id": assignment.course_id,
            "course_name": course_by_id.get(assignment.course_id).name
            if assignment.course_id in course_by_id
            else "Unknown course",
            "title": assignment.name,
            "due_at": _iso(assignment.due_at),
            "status": assignment.submission_status,
        }
        for assignment in open_assignments[:12]
    ]

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    events = session.exec(
        select(ScheduleEvent)
        .where(ScheduleEvent.start_at >= day_start)
        .where(ScheduleEvent.start_at < day_end)
        .order_by(ScheduleEvent.start_at)
    ).all()
    schedule = [
        {
            "id": event.id,
            "course_id": event.course_id,
            "course_name": course_by_id.get(event.course_id).name
            if event.course_id in course_by_id
            else None,
            "title": event.title,
            "start_at": _iso(event.start_at),
            "end_at": _iso(event.end_at),
            "location": event.location,
        }
        for event in events
    ]

    return {
        "semester_label": Counter(term_names).most_common(1)[0][0]
        if term_names
        else "Current semester",
        "course_count": len(courses),
        "semester_progress_percent": round(sum(progress_values) / len(progress_values))
        if progress_values
        else None,
        "courses": course_rows,
        "deadlines": deadlines,
        "today_schedule": schedule,
    }


def build_library(session: Session) -> dict[str, object]:
    """Expose locally mirrored files and generated cards without leaking local paths."""
    courses = session.exec(select(Course).order_by(Course.course_code, Course.name)).all()
    materials = session.exec(
        select(Material).order_by(Material.remote_updated_at.desc(), Material.id.desc())
    ).all()
    cards = session.exec(select(Flashcard).order_by(Flashcard.id.desc())).all()
    materials_by_course: dict[int, list[Material]] = {}
    for material in materials:
        materials_by_course.setdefault(material.course_id, []).append(material)
    cards_by_course = Counter(card.course_id for card in cards)

    course_rows = []
    for course in courses:
        course_materials = materials_by_course.get(course.id or -1, [])
        course_rows.append(
            {
                "id": course.id,
                "name": course.name,
                "course_code": course.course_code,
                "material_count": len(course_materials),
                "flashcard_count": cards_by_course.get(course.id, 0),
                "materials": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "week": item.week,
                        "category": item.category,
                        "size_bytes": item.size_bytes,
                        "updated_at": _iso(item.remote_updated_at),
                    }
                    for item in course_materials[:8]
                ],
            }
        )
    return {
        "courses": course_rows,
        "total_materials": len(materials),
        "total_flashcards": len(cards),
    }
