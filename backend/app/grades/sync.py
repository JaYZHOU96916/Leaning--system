import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.canvas.client import CanvasClient
from app.models import Assignment, AssignmentGroup, AssignmentSubmission, Course
from app.sync.assignments import assignment_from_canvas, parse_canvas_datetime


@dataclass(frozen=True)
class GradeSyncSummary:
    groups: int
    assignments: int


class GradeDataSyncService:
    def __init__(self, client: CanvasClient):
        self.client = client

    async def sync_course(self, session: Session, course: Course) -> GradeSyncSummary:
        if course.id is None:
            raise ValueError("Course must be persisted before grade sync")
        payloads = await self.client.get_all(
            f"/courses/{course.canvas_id}/assignment_groups",
            params={"include[]": "assignments", "per_page": 100},
        )
        assignment_count = 0
        for group_payload in payloads:
            if not isinstance(group_payload, dict) or group_payload.get("id") is None:
                continue
            group = session.exec(
                select(AssignmentGroup).where(
                    AssignmentGroup.canvas_id == int(group_payload["id"])
                )
            ).first()
            values = {
                "canvas_id": int(group_payload["id"]),
                "course_id": course.id,
                "name": str(group_payload.get("name") or "Ungrouped"),
                "group_weight": float(group_payload.get("group_weight") or 0),
                "position": group_payload.get("position"),
                "updated_at": datetime.now(UTC),
            }
            if group is None:
                group = AssignmentGroup(**values)
                session.add(group)
                session.flush()
            else:
                for key, value in values.items():
                    setattr(group, key, value)
            for assignment_payload in group_payload.get("assignments") or []:
                if not isinstance(assignment_payload, dict) or assignment_payload.get("id") is None:
                    continue
                assignment_values = assignment_from_canvas(
                    assignment_payload,
                    course_id=course.id,
                    now=datetime.now(UTC),
                )
                assignment_values["assignment_group_id"] = group.id
                existing = session.exec(
                    select(Assignment).where(
                        Assignment.canvas_id == assignment_values["canvas_id"]
                    )
                ).first()
                if existing is None:
                    session.add(Assignment(**assignment_values))
                else:
                    for key, value in assignment_values.items():
                        setattr(existing, key, value)
                assignment_count += 1
        session.commit()
        return GradeSyncSummary(len(payloads), assignment_count)

    async def sync_submission_history(
        self,
        session: Session,
        course: Course,
        *,
        user_id: str = "self",
    ) -> int:
        if course.id is None:
            raise ValueError("Course must be persisted before submission sync")
        assignments = session.exec(
            select(Assignment).where(Assignment.course_id == course.id)
        ).all()
        created = 0
        for assignment in assignments:
            payload = await self.client.get(
                f"/courses/{course.canvas_id}/assignments/{assignment.canvas_id}/submissions/{user_id}",
                params={"include[]": ["submission_history", "rubric_assessment"]},
            )
            data = payload.json()
            history = data.get("submission_history") or [data]
            for submission in history:
                if not isinstance(submission, dict) or submission.get("id") is None:
                    continue
                canvas_id = int(submission["id"])
                existing = session.exec(
                    select(AssignmentSubmission).where(
                        AssignmentSubmission.canvas_id == canvas_id
                    )
                ).first()
                values: dict[str, Any] = {
                    "canvas_id": canvas_id,
                    "assignment_id": assignment.id,
                    "attempt": int(submission.get("attempt") or 0),
                    "submitted_at": parse_canvas_datetime(submission.get("submitted_at")),
                    "score": submission.get("score"),
                    "grade": submission.get("grade"),
                    "workflow_state": submission.get("workflow_state"),
                    "late": bool(submission.get("late")),
                    "feedback": submission.get("feedback") or submission.get("comments"),
                    "rubric_json": json.dumps(
                        submission.get("rubric_assessment") or {},
                        ensure_ascii=False,
                    ),
                    "raw_json": json.dumps(submission, ensure_ascii=False),
                    "updated_at": datetime.now(UTC),
                }
                if existing is None:
                    session.add(AssignmentSubmission(**values))
                    created += 1
                else:
                    for key, value in values.items():
                        setattr(existing, key, value)
        session.commit()
        return created
