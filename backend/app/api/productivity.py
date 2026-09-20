from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.models import Assignment, Course, FocusSession, TodoItem
from app.productivity.analytics import focus_analytics
from app.productivity.focus import FocusSessionService
from app.productivity.todos import aggregate_today

router = APIRouter(prefix="/api", tags=["productivity"])


class TodoCreate(BaseModel):
    title: str
    course_id: int | None = None
    assignment_id: int | None = None
    due_at: datetime | None = None
    priority: int = 0


class FocusStart(BaseModel):
    course_id: int | None = None
    assignment_id: int | None = None
    notes: str | None = None


def serialize_focus(focus: FocusSession) -> dict[str, object]:
    return {
        "id": focus.id,
        "course_id": focus.course_id,
        "assignment_id": focus.assignment_id,
        "status": focus.status,
        "started_at": focus.started_at,
        "ended_at": focus.ended_at,
        "duration_seconds": focus.duration_seconds,
    }


@router.get("/todos/today")
def today_todos(session: Session = Depends(get_session)) -> dict[str, object]:
    items = aggregate_today(session)
    return {"items": [item.__dict__ for item in items]}


@router.post("/todos", status_code=201)
def create_todo(payload: TodoCreate, session: Session = Depends(get_session)) -> dict[str, object]:
    if payload.course_id is not None and session.get(Course, payload.course_id) is None:
        raise HTTPException(status_code=404, detail="Course not found")
    if payload.assignment_id is not None and session.get(Assignment, payload.assignment_id) is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    todo = TodoItem(**payload.model_dump(), is_manual=True)
    session.add(todo)
    session.commit()
    session.refresh(todo)
    return todo.model_dump()


@router.patch("/todos/{todo_id}/complete")
def complete_todo(todo_id: int, session: Session = Depends(get_session)) -> dict[str, object]:
    todo = session.get(TodoItem, todo_id)
    if todo is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    todo.status = "completed"
    todo.completed_at = datetime.now(UTC)
    session.add(todo)
    session.commit()
    return todo.model_dump()


@router.post("/focus/start", status_code=201)
def start_focus(payload: FocusStart, session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        focus = FocusSessionService(session).start(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return serialize_focus(focus)


def mutate_focus(focus_id: int, action: str, session: Session) -> dict[str, object]:
    focus = session.get(FocusSession, focus_id)
    if focus is None:
        raise HTTPException(status_code=404, detail="Focus session not found")
    try:
        focus = getattr(FocusSessionService(session), action)(focus)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return serialize_focus(focus)


@router.post("/focus/{focus_id}/pause")
def pause_focus(focus_id: int, session: Session = Depends(get_session)) -> dict[str, object]:
    return mutate_focus(focus_id, "pause", session)


@router.post("/focus/{focus_id}/resume")
def resume_focus(focus_id: int, session: Session = Depends(get_session)) -> dict[str, object]:
    return mutate_focus(focus_id, "resume", session)


@router.post("/focus/{focus_id}/complete")
def complete_focus(focus_id: int, session: Session = Depends(get_session)) -> dict[str, object]:
    return mutate_focus(focus_id, "complete", session)


@router.get("/focus/active")
def active_focus(session: Session = Depends(get_session)) -> dict[str, object | None]:
    focus = FocusSessionService(session).active()
    return {"focus": serialize_focus(focus) if focus else None}


@router.get("/analytics/focus")
def focus_stats(session: Session = Depends(get_session)) -> dict[str, object]:
    return focus_analytics(session)
