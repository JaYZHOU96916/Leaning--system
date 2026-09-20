from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.canvas.client import CanvasClient
from app.models import Course
from app.sync.assignments import parse_canvas_datetime


@dataclass(frozen=True)
class CourseSyncSummary:
    fetched: int
    created: int
    updated: int
    unchanged: int


def course_from_canvas(payload: dict[str, Any]) -> dict[str, Any]:
    term = payload.get("term") or {}
    return {
        "canvas_id": int(payload["id"]),
        "name": str(payload.get("name") or f"Course {payload['id']}"),
        "course_code": payload.get("course_code"),
        "term_name": term.get("name"),
        "workflow_state": str(payload.get("workflow_state") or "available"),
        "start_at": parse_canvas_datetime(payload.get("start_at")),
        "end_at": parse_canvas_datetime(payload.get("end_at")),
        "html_url": payload.get("html_url"),
    }


class CourseSyncService:
    def __init__(self, client: CanvasClient):
        self.client = client

    @staticmethod
    def _same_value(current: object, incoming: object) -> bool:
        if isinstance(current, datetime) and isinstance(incoming, datetime):
            if current.tzinfo is None:
                current = current.replace(tzinfo=UTC)
            if incoming.tzinfo is None:
                incoming = incoming.replace(tzinfo=UTC)
        return current == incoming

    async def sync_courses(
        self,
        session: Session,
        *,
        now: datetime | None = None,
    ) -> CourseSyncSummary:
        now = now or datetime.now(UTC)
        payloads = await self.client.get_all(
            "/courses",
            params={
                "enrollment_state": "active",
                "include[]": "term",
                "per_page": 100,
            },
        )
        created = updated = unchanged = 0
        for payload in payloads:
            if not isinstance(payload, dict) or "id" not in payload:
                continue
            values = course_from_canvas(payload)
            existing = session.exec(
                select(Course).where(Course.canvas_id == values["canvas_id"])
            ).first()
            if existing is None:
                session.add(Course(**values))
                created += 1
                continue
            if all(
                self._same_value(getattr(existing, key), value)
                for key, value in values.items()
            ):
                unchanged += 1
                continue
            for key, value in values.items():
                setattr(existing, key, value)
            existing.updated_at = now
            updated += 1
        session.commit()
        return CourseSyncSummary(len(payloads), created, updated, unchanged)
