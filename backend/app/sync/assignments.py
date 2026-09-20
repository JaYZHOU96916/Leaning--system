from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.canvas.client import CanvasClient
from app.models import Assignment, Course


def parse_canvas_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def determine_submission_status(payload: dict[str, Any], *, now: datetime) -> str:
    submission = payload.get("submission") or {}
    submitted_at = parse_canvas_datetime(submission.get("submitted_at"))
    score = submission.get("score")
    if score is not None:
        return "graded"
    if submitted_at is not None or submission.get("workflow_state") in {
        "submitted",
        "pending_review",
    }:
        return "submitted"
    due_at = parse_canvas_datetime(payload.get("due_at"))
    if due_at and due_at < now:
        return "overdue"
    return "unsubmitted"


def assignment_from_canvas(
    payload: dict[str, Any],
    *,
    course_id: int,
    now: datetime,
) -> dict[str, Any]:
    submission = payload.get("submission") or {}
    submitted_at = parse_canvas_datetime(submission.get("submitted_at"))
    due_at = parse_canvas_datetime(payload.get("due_at"))
    remote_updated_at = parse_canvas_datetime(payload.get("updated_at"))
    return {
        "canvas_id": int(payload["id"]),
        "course_id": course_id,
        "assignment_group_id": None,
        "name": str(payload.get("name") or f"Assignment {payload['id']}"),
        "description": payload.get("description"),
        "due_at": due_at,
        "lock_at": parse_canvas_datetime(payload.get("lock_at")),
        "points_possible": payload.get("points_possible"),
        "score": submission.get("score"),
        "remote_updated_at": remote_updated_at,
        "submission_status": determine_submission_status(payload, now=now),
        "submitted_at": submitted_at,
        "html_url": payload.get("html_url"),
    }


@dataclass(frozen=True)
class AssignmentSyncSummary:
    course_canvas_id: int
    fetched: int
    created: int
    updated: int
    unchanged: int


class AssignmentSyncService:
    def __init__(self, client: CanvasClient):
        self.client = client

    async def sync_course(
        self,
        session: Session,
        course: Course,
        *,
        now: datetime | None = None,
    ) -> AssignmentSyncSummary:
        if course.id is None:
            raise ValueError("Course must be persisted before assignment sync")
        now = now or datetime.now(UTC)
        payloads = await self.client.get_all(
            f"/courses/{course.canvas_id}/assignments",
            params={"include[]": "submission", "per_page": 100, "order_by": "updated_at"},
        )
        created = updated = unchanged = 0
        for payload in payloads:
            if not isinstance(payload, dict) or "id" not in payload:
                continue
            values = assignment_from_canvas(payload, course_id=course.id, now=now)
            existing = session.exec(
                select(Assignment).where(Assignment.canvas_id == values["canvas_id"])
            ).first()
            if existing is None:
                session.add(Assignment(**values))
                created += 1
                continue
            remote_updated_at = values["remote_updated_at"]
            if (
                remote_updated_at is not None
                and existing.remote_updated_at is not None
                and remote_updated_at <= existing.remote_updated_at
            ):
                # A due date can become overdue locally even when Canvas has not changed.
                existing.submission_status = values["submission_status"]
                existing.updated_at = now
                unchanged += 1
                continue
            for key, value in values.items():
                setattr(existing, key, value)
            existing.updated_at = now
            updated += 1
        session.commit()
        return AssignmentSyncSummary(course.canvas_id, len(payloads), created, updated, unchanged)

    async def sync_all_courses(
        self,
        session: Session,
        *,
        now: datetime | None = None,
    ) -> list[AssignmentSyncSummary]:
        return [
            await self.sync_course(session, course, now=now)
            for course in session.exec(select(Course)).all()
        ]
