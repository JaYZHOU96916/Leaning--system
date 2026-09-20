import html
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlmodel import Session, select

from app.models import Assignment, AssignmentGroup, AssignmentSubmission, Course


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def build_course_snapshot(session: Session, course_id: int) -> dict[str, Any]:
    course = session.get(Course, course_id)
    if course is None:
        raise ValueError("Course not found")
    groups = session.exec(
        select(AssignmentGroup)
        .where(AssignmentGroup.course_id == course_id)
        .order_by(AssignmentGroup.position)
    ).all()
    assignments = session.exec(
        select(Assignment).where(Assignment.course_id == course_id).order_by(Assignment.due_at)
    ).all()
    assignment_ids = [assignment.id for assignment in assignments if assignment.id is not None]
    submissions = (
        session.exec(
            select(AssignmentSubmission).where(
                AssignmentSubmission.assignment_id.in_(assignment_ids)
            )
        ).all()
        if assignment_ids
        else []
    )
    return {
        "snapshot_version": "1",
        "exported_at": datetime.now(UTC).isoformat(),
        "course": {key: _json_value(value) for key, value in course.model_dump().items()},
        "assignment_groups": [
            {key: _json_value(value) for key, value in group.model_dump().items()}
            for group in groups
        ],
        "assignments": [
            {key: _json_value(value) for key, value in assignment.model_dump().items()}
            for assignment in assignments
        ],
        "submission_history": [
            {key: _json_value(value) for key, value in submission.model_dump().items()}
            for submission in submissions
        ],
    }


def snapshot_to_html(snapshot: dict[str, Any]) -> str:
    course = snapshot["course"]
    rows = []
    for assignment in snapshot["assignments"]:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(assignment.get('name') or ''))}</td>"
            f"<td>{html.escape(str(assignment.get('submission_status') or ''))}</td>"
            f"<td>{html.escape(str(assignment.get('score') or ''))}</td>"
            f"<td>{html.escape(str(assignment.get('due_at') or ''))}</td>"
            "</tr>"
        )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Academic OS snapshot - {html.escape(str(course.get('name')))}</title>"
        "<style>body{font-family:system-ui;margin:2rem}table{border-collapse:collapse}"
        "td,th{border:1px solid #ddd;padding:.5rem;text-align:left}</style></head><body>"
        f"<h1>{html.escape(str(course.get('name')))}</h1>"
        f"<p>导出时间：{html.escape(str(snapshot.get('exported_at')))}</p>"
        "<table><thead><tr><th>Assignment</th><th>Status</th><th>Score</th><th>Due</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></body></html>"
    )


def write_course_snapshot(
    session: Session,
    course_id: int,
    *,
    output_dir: Path,
    format: Literal["json", "html"],
) -> Path:
    snapshot = build_course_snapshot(session, course_id)
    course = snapshot["course"]
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = "json" if format == "json" else "html"
    destination = output_dir / f"course-{course['canvas_id']}-snapshot.{suffix}"
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=output_dir,
        prefix=f".{destination.name}.",
        delete=False,
    ) as temporary:
        if format == "json":
            json.dump(snapshot, temporary, ensure_ascii=False, indent=2)
        else:
            temporary.write(snapshot_to_html(snapshot))
        temporary_path = Path(temporary.name)
    temporary_path.replace(destination)
    return destination
