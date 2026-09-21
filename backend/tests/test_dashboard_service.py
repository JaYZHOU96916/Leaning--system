from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.dashboard.service import build_library, build_overview
from app.db import create_db_and_tables
from app.models import Assignment, Course, Flashcard, Material, ScheduleEvent
from sqlmodel import Session, create_engine


def test_overview_collects_deadlines_schedule_and_course_progress(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'dashboard.db'}")
    create_db_and_tables(engine)
    now = datetime(2026, 9, 21, 8, tzinfo=UTC)
    with Session(engine) as session:
        course = Course(
            canvas_id=1,
            name="Design Systems",
            course_code="INFO30005",
            term_name="Semester 2, 2026",
            start_at=now - timedelta(days=10),
            end_at=now + timedelta(days=10),
        )
        session.add(course)
        session.commit()
        session.refresh(course)
        session.add_all(
            [
                Assignment(
                    canvas_id=2,
                    course_id=course.id,
                    name="Prototype review",
                    due_at=now + timedelta(days=2),
                    submission_status="unsubmitted",
                ),
                Assignment(
                    canvas_id=3,
                    course_id=course.id,
                    name="Reading response",
                    submission_status="submitted",
                ),
                ScheduleEvent(
                    canvas_id=4,
                    course_id=course.id,
                    title="Design studio",
                    start_at=now + timedelta(hours=2),
                    location="Babel 305",
                ),
            ]
        )
        session.commit()
        overview = build_overview(session, now=now)

    assert overview["semester_label"] == "Semester 2, 2026"
    assert overview["semester_progress_percent"] == 50
    assert overview["courses"] == [
        {
            "id": 1,
            "name": "Design Systems",
            "course_code": "INFO30005",
            "term_name": "Semester 2, 2026",
            "assignment_total": 2,
            "assignment_completed": 1,
            "semester_progress_percent": 50,
            "next_due_at": (now + timedelta(days=2)).isoformat(),
        }
    ]
    assert overview["deadlines"][0]["title"] == "Prototype review"
    assert overview["today_schedule"][0]["location"] == "Babel 305"


def test_library_groups_materials_and_cards_by_course(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'library.db'}")
    create_db_and_tables(engine)
    with Session(engine) as session:
        course = Course(canvas_id=10, name="Data Modelling")
        session.add(course)
        session.commit()
        session.refresh(course)
        material = Material(
            canvas_file_id=11,
            course_id=course.id,
            name="Week 1 slides.pdf",
            sha256="abc123",
            week="Week 01",
            category="Lecture",
            size_bytes=512,
        )
        session.add(material)
        session.commit()
        session.refresh(material)
        session.add(
            Flashcard(
                course_id=course.id,
                material_id=material.id,
                question="What is a key?",
                answer="A unique identifier.",
            )
        )
        session.commit()
        library = build_library(session)

    assert library["total_materials"] == 1
    assert library["total_flashcards"] == 1
    assert library["courses"][0]["flashcard_count"] == 1
    assert library["courses"][0]["materials"][0]["week"] == "Week 01"
