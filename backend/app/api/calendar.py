from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlmodel import Session

from app.calendar.feed import build_calendar_feed
from app.db import get_session

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/feed.ics", response_class=Response)
def calendar_feed(
    course_id: int | None = Query(default=None),
    include_assignments: bool = Query(default=True),
    include_events: bool = Query(default=True),
    session: Session = Depends(get_session),
) -> Response:
    payload = build_calendar_feed(
        session,
        course_id=course_id,
        include_assignments=include_assignments,
        include_events=include_events,
    )
    return Response(
        content=payload,
        media_type="text/calendar",
        headers={"Content-Disposition": 'inline; filename="academic-os.ics"'},
    )
