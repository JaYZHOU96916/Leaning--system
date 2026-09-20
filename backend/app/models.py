from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampedModel(SQLModel):
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)


class Course(TimestampedModel, table=True):
    __tablename__ = "course"

    id: int | None = Field(default=None, primary_key=True)
    canvas_id: int = Field(index=True, unique=True, nullable=False)
    name: str
    course_code: str | None = None
    term_name: str | None = None
    workflow_state: str = "available"
    start_at: datetime | None = None
    end_at: datetime | None = None
    html_url: str | None = None


class AssignmentGroup(TimestampedModel, table=True):
    __tablename__ = "assignment_group"

    id: int | None = Field(default=None, primary_key=True)
    canvas_id: int = Field(index=True, unique=True, nullable=False)
    course_id: int = Field(foreign_key="course.id", index=True, nullable=False)
    name: str
    group_weight: float = 0.0
    position: int | None = None


class Assignment(TimestampedModel, table=True):
    __tablename__ = "assignment"

    id: int | None = Field(default=None, primary_key=True)
    canvas_id: int = Field(index=True, unique=True, nullable=False)
    course_id: int = Field(foreign_key="course.id", index=True, nullable=False)
    assignment_group_id: int | None = Field(
        default=None,
        foreign_key="assignment_group.id",
        index=True,
    )
    name: str
    description: str | None = None
    due_at: datetime | None = Field(default=None, index=True)
    lock_at: datetime | None = None
    points_possible: float | None = None
    score: float | None = None
    remote_updated_at: datetime | None = None
    submission_status: str = "unsubmitted"
    submitted_at: datetime | None = None
    html_url: str | None = None


class AlertDelivery(TimestampedModel, table=True):
    __tablename__ = "alert_delivery"

    id: int | None = Field(default=None, primary_key=True)
    assignment_id: int = Field(foreign_key="assignment.id", index=True, nullable=False)
    alert_level: str
    channel: str = "webhook"
    dedupe_key: str = Field(index=True, unique=True, nullable=False)
    status: str = "pending"
    sent_at: datetime | None = None
    error: str | None = None


class ScheduleEvent(TimestampedModel, table=True):
    __tablename__ = "schedule_event"

    id: int | None = Field(default=None, primary_key=True)
    canvas_id: int = Field(index=True, unique=True, nullable=False)
    course_id: int | None = Field(default=None, foreign_key="course.id", index=True)
    title: str
    event_type: str = "event"
    start_at: datetime = Field(index=True)
    end_at: datetime | None = None
    all_day: bool = False
    location: str | None = None
    html_url: str | None = None


class Material(TimestampedModel, table=True):
    __tablename__ = "material"

    id: int | None = Field(default=None, primary_key=True)
    canvas_file_id: int = Field(index=True, unique=True, nullable=False)
    course_id: int = Field(foreign_key="course.id", index=True, nullable=False)
    name: str
    local_path: str | None = None
    sha256: str = Field(index=True, nullable=False)
    remote_updated_at: datetime | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    week: str | None = None
    category: str | None = None
    download_url: str | None = None


class FocusSession(TimestampedModel, table=True):
    __tablename__ = "focus_session"

    id: int | None = Field(default=None, primary_key=True)
    course_id: int | None = Field(default=None, foreign_key="course.id", index=True)
    assignment_id: int | None = Field(default=None, foreign_key="assignment.id", index=True)
    started_at: datetime = Field(default_factory=utcnow, index=True)
    ended_at: datetime | None = None
    duration_seconds: int = 0
    status: str = "running"
    notes: str | None = None


class Flashcard(TimestampedModel, table=True):
    __tablename__ = "flashcard"

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id", index=True, nullable=False)
    material_id: int | None = Field(default=None, foreign_key="material.id", index=True)
    question: str
    answer: str
    source: str | None = None


class TodoItem(TimestampedModel, table=True):
    __tablename__ = "todo_item"

    id: int | None = Field(default=None, primary_key=True)
    course_id: int | None = Field(default=None, foreign_key="course.id", index=True)
    assignment_id: int | None = Field(default=None, foreign_key="assignment.id", index=True)
    title: str
    due_at: datetime | None = Field(default=None, index=True)
    status: str = "open"
    priority: int = 0
    is_manual: bool = True
    completed_at: datetime | None = None
