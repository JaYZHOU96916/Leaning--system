from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.canvas.client import CanvasClient
from app.core.config import Settings
from app.db import get_session
from app.grades.sync import GradeDataSyncService
from app.materials.sync import MaterialSyncService
from app.models import Course
from app.sync.assignments import AssignmentSyncService
from app.sync.courses import CourseSyncService

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/courses")
async def sync_courses(session: Session = Depends(get_session)) -> dict[str, int]:
    """Bootstrap or refresh the local course catalog from Canvas."""

    async with CanvasClient() as client:
        summary = await CourseSyncService(client).sync_courses(session)
    return summary.__dict__


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
        service = AssignmentSyncService(client)
        if course_id is not None:
            summaries = [await service.sync_course(session, courses[0])]
        else:
            summaries = await service.sync_all_courses(session)
    return {"courses": [summary.__dict__ for summary in summaries]}


@router.post("/materials")
async def sync_materials(
    course_id: int | None = None,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    statement = select(Course)
    if course_id is not None:
        statement = statement.where(Course.id == course_id)
    courses = session.exec(statement).all()
    if course_id is not None and not courses:
        raise HTTPException(status_code=404, detail="Course not found")
    settings = Settings()
    async with CanvasClient(settings) as client:
        service = MaterialSyncService(client)
        results = [
            await service.sync_course(
                session,
                course,
                root_dir=Path(settings.materials_root_dir),
            )
            for course in courses
        ]
    return {"courses": [result.__dict__ for result in results]}


@router.post("/grades")
async def sync_grades(
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
        service = GradeDataSyncService(client)
        results = [await service.sync_course(session, course) for course in courses]
    return {"courses": [result.__dict__ for result in results]}


@router.post("/submissions")
async def sync_submissions(
    course_id: int | None = None,
    session: Session = Depends(get_session),
) -> dict[str, int]:
    statement = select(Course)
    if course_id is not None:
        statement = statement.where(Course.id == course_id)
    courses = session.exec(statement).all()
    if course_id is not None and not courses:
        raise HTTPException(status_code=404, detail="Course not found")
    async with CanvasClient() as client:
        service = GradeDataSyncService(client)
        created = sum(
            [await service.sync_submission_history(session, course) for course in courses],
            0,
        )
    return {"submissions_created_or_updated": created}
