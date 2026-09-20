from datetime import UTC, datetime

from sqlmodel import Session, select

from app.models import FocusSession


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def elapsed_seconds(started_at: datetime, now: datetime) -> int:
    return max(0, int((as_utc(now) - as_utc(started_at)).total_seconds()))


class FocusSessionService:
    def __init__(self, session: Session):
        self.session = session

    def active(self) -> FocusSession | None:
        return self.session.exec(
            select(FocusSession).where(FocusSession.status.in_(["running", "paused"]))
        ).first()

    def start(
        self,
        *,
        course_id: int | None = None,
        assignment_id: int | None = None,
        notes: str | None = None,
        now: datetime | None = None,
    ) -> FocusSession:
        if self.active() is not None:
            raise ValueError("A focus session is already active")
        now = now or datetime.now(UTC)
        focus = FocusSession(
            course_id=course_id,
            assignment_id=assignment_id,
            started_at=now,
            active_started_at=now,
            status="running",
            notes=notes,
        )
        self.session.add(focus)
        self.session.commit()
        self.session.refresh(focus)
        return focus

    def pause(self, focus: FocusSession, *, now: datetime | None = None) -> FocusSession:
        if focus.status != "running" or focus.active_started_at is None:
            raise ValueError("Only a running focus session can be paused")
        now = now or datetime.now(UTC)
        focus.duration_seconds += elapsed_seconds(focus.active_started_at, now)
        focus.active_started_at = None
        focus.paused_at = now
        focus.status = "paused"
        focus.updated_at = now
        self.session.add(focus)
        self.session.commit()
        self.session.refresh(focus)
        return focus

    def resume(self, focus: FocusSession, *, now: datetime | None = None) -> FocusSession:
        if focus.status != "paused":
            raise ValueError("Only a paused focus session can be resumed")
        now = now or datetime.now(UTC)
        focus.active_started_at = now
        focus.paused_at = None
        focus.status = "running"
        focus.updated_at = now
        self.session.add(focus)
        self.session.commit()
        self.session.refresh(focus)
        return focus

    def complete(self, focus: FocusSession, *, now: datetime | None = None) -> FocusSession:
        if focus.status not in {"running", "paused"}:
            raise ValueError("Only an active focus session can be completed")
        now = now or datetime.now(UTC)
        if focus.status == "running" and focus.active_started_at is not None:
            focus.duration_seconds += elapsed_seconds(focus.active_started_at, now)
        focus.active_started_at = None
        focus.ended_at = now
        focus.status = "completed"
        focus.updated_at = now
        self.session.add(focus)
        self.session.commit()
        self.session.refresh(focus)
        return focus
