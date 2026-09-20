from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.config import Settings
from app.db import get_session
from app.grades.engine import GradeGroup, GradeItem, WeightedGradeCalculator, decimal
from app.models import Assignment, AssignmentGroup, Course
from app.snapshots.service import write_course_snapshot

router = APIRouter(prefix="/api/courses", tags=["grades"])


class WhatIfRequest(BaseModel):
    target_percent: Decimal = Field(ge=0, le=100)


def _grade_groups(session: Session, course_id: int) -> list[GradeGroup]:
    groups = session.exec(
        select(AssignmentGroup).where(AssignmentGroup.course_id == course_id)
    ).all()
    result = []
    for group in groups:
        assignments = session.exec(
            select(Assignment).where(Assignment.assignment_group_id == group.id)
        ).all()
        result.append(
            GradeGroup(
                name=group.name,
                weight_percent=decimal(group.group_weight),
                items=tuple(
                    GradeItem(
                        id=assignment.id or assignment.canvas_id,
                        name=assignment.name,
                        points_possible=decimal(assignment.points_possible or 0),
                        score=decimal(assignment.score) if assignment.score is not None else None,
                    )
                    for assignment in assignments
                    if (assignment.points_possible or 0) > 0
                ),
            )
        )
    return result


@router.get("/{course_id}/grades/summary")
def grade_summary(course_id: int, session: Session = Depends(get_session)) -> dict[str, object]:
    if session.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail="Course not found")
    groups = _grade_groups(session, course_id)
    if not groups:
        return {"groups": [], "calculation": None}
    calculation = WeightedGradeCalculator(groups).calculate()
    return {
        "groups": [group.name for group in groups],
        "calculation": {
            key: str(value) if isinstance(value, Decimal) else value
            for key, value in calculation.__dict__.items()
        },
    }


@router.post("/{course_id}/grades/what-if")
def grade_what_if(
    course_id: int,
    request: WhatIfRequest,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    if session.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail="Course not found")
    groups = _grade_groups(session, course_id)
    if not groups:
        raise HTTPException(status_code=400, detail="No assignment groups available")
    result = WeightedGradeCalculator(groups).required_average_on_remaining(
        request.target_percent
    )
    return {
        key: str(value) if isinstance(value, Decimal) else value
        for key, value in result.__dict__.items()
    }


@router.get("/{course_id}/snapshot")
def course_snapshot(
    course_id: int,
    format: Literal["json", "html"] = "json",
    session: Session = Depends(get_session),
) -> FileResponse:
    if session.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail="Course not found")
    path = write_course_snapshot(
        session,
        course_id,
        output_dir=Path(Settings().snapshots_root_dir),
        format=format,
    )
    media_type = "application/json" if format == "json" else "text/html"
    return FileResponse(path, media_type=media_type, filename=path.name)
