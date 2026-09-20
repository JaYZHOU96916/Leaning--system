from decimal import Decimal
from pathlib import Path

from app.db import create_db_and_tables
from app.grades.engine import GradeGroup, GradeItem, WeightedGradeCalculator, decimal
from app.grades.sync import GradeDataSyncService
from app.models import Assignment, AssignmentGroup, AssignmentSubmission, Course
from app.snapshots.service import build_course_snapshot, snapshot_to_html, write_course_snapshot
from sqlmodel import Session, create_engine, select


def test_weighted_grade_and_required_final_score() -> None:
    groups = [
        GradeGroup(
            name="Assignments",
            weight_percent=decimal("40"),
            items=(
                GradeItem(1, "A1", decimal("100"), decimal("80")),
                GradeItem(2, "A2", decimal("100"), decimal("90")),
            ),
        ),
        GradeGroup(
            name="Final",
            weight_percent=decimal("60"),
            items=(GradeItem(3, "Final Exam", decimal("100"), None),),
        ),
    ]
    calculator = WeightedGradeCalculator(groups)
    calculation = calculator.calculate()
    required = calculator.required_average_on_remaining(80)

    assert calculation.current_weighted_percent == Decimal("34")
    assert calculation.max_possible_percent == Decimal("94")
    assert required.required_average_percent == Decimal("76.66666666666666666666666667")
    assert required.required_points == required.required_average_percent
    assert required.feasible is True


def test_grade_boundaries_are_explicit() -> None:
    groups = [
        GradeGroup(
            name="Final",
            weight_percent=decimal("100"),
            items=(GradeItem(1, "Final", decimal("50"), None),),
        )
    ]
    calculator = WeightedGradeCalculator(groups)
    assert calculator.required_average_on_remaining(0).required_average_percent == Decimal("0")
    impossible = calculator.required_average_on_remaining(101)
    assert impossible.feasible is False
    assert "maximum" in (impossible.reason or "")


async def test_canvas_assignment_groups_sync_with_scores(tmp_path: Path) -> None:
    class FakeCanvasClient:
        async def get_all(self, url: str, **kwargs):
            return [
                {
                    "id": 601,
                    "name": "Quizzes",
                    "group_weight": 30,
                    "position": 1,
                    "assignments": [
                        {
                            "id": 602,
                            "name": "Quiz 1",
                            "points_possible": 20,
                            "submission": {"score": 18},
                        }
                    ],
                }
            ]

    engine = create_engine(
        f"sqlite:///{tmp_path / 'grade-sync.db'}",
        connect_args={"check_same_thread": False},
    )
    create_db_and_tables(engine)
    with Session(engine) as session:
        course = Course(canvas_id=600, name="Statistics")
        session.add(course)
        session.commit()
        session.refresh(course)
        summary = await GradeDataSyncService(FakeCanvasClient()).sync_course(session, course)
        group = session.exec(select(AssignmentGroup)).one()
        assignment = session.exec(select(Assignment)).one()

    assert summary.groups == 1
    assert summary.assignments == 1
    assert group.group_weight == 30
    assert assignment.score == 18


def test_snapshot_exports_assignments_and_submission_feedback(tmp_path: Path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'phase3.db'}",
        connect_args={"check_same_thread": False},
    )
    create_db_and_tables(engine)
    with Session(engine) as session:
        course = Course(canvas_id=501, name="Machine Learning")
        session.add(course)
        session.commit()
        session.refresh(course)
        group = AssignmentGroup(
            canvas_id=502,
            course_id=course.id,
            name="Projects",
            group_weight=100,
        )
        session.add(group)
        session.commit()
        session.refresh(group)
        assignment = Assignment(
            canvas_id=503,
            course_id=course.id,
            assignment_group_id=group.id,
            name="Capstone",
            points_possible=100,
            score=88,
        )
        session.add(assignment)
        session.commit()
        session.refresh(assignment)
        session.add(
            AssignmentSubmission(
                canvas_id=504,
                assignment_id=assignment.id,
                attempt=1,
                score=88,
                feedback="Strong analysis",
                rubric_json='{"criterion":{"points":4}}',
            )
        )
        session.commit()
        snapshot = build_course_snapshot(session, course.id)
        html = snapshot_to_html(snapshot)
        json_path = write_course_snapshot(
            session,
            course.id,
            output_dir=tmp_path / "snapshots",
            format="json",
        )

    assert snapshot["submission_history"][0]["feedback"] == "Strong analysis"
    assert "Capstone" in html
    assert json_path.is_file()
