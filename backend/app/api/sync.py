from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.canvas.client import CanvasClient
from app.db import get_session
from app.models import Course
from app.sync.assignments import AssignmentSyncService

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/assignments")
async def sync_assignments(
    course_id: int | None = None,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    statement = select(Course)
    if course_id is not None:
        statement = statement.where(Course.id == course_id)
    courses = session.exec(statement).all()
    if course_id is not None and not courses:
        raise HTTPException(status_code=404, detail="Course not found")
    async with CanvasClient() as client:
        summaries = await AssignmentSyncService(client).sync_all_courses(session)
    return {"courses": [summary.__dict__ for summary in summaries]}
