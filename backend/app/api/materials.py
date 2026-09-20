import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlmodel import Session, select
from starlette.background import BackgroundTask

from app.ai.flashcards import generate_flashcards_for_job, to_anki_tsv
from app.core.config import Settings
from app.db import get_engine, get_session
from app.materials.archive import build_course_zip
from app.models import Course, Flashcard, FlashcardJob, Material

router = APIRouter(prefix="/api", tags=["materials"])


def _cleanup_archive(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


@router.get("/courses/{course_id}/materials.zip")
def download_course_materials(
    course_id: int,
    session: Session = Depends(get_session),
) -> FileResponse:
    if session.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail="Course not found")
    zip_path = build_course_zip(
        session,
        course_id,
        materials_root=Path(Settings().materials_root_dir),
    )
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"course-{course_id}-materials.zip",
        background=BackgroundTask(_cleanup_archive, zip_path.parent),
    )


@router.post("/materials/{material_id}/flashcards/generate", status_code=202)
async def start_flashcard_generation(
    material_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> dict[str, int | str]:
    material = session.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    job = FlashcardJob(course_id=material.course_id, material_id=material.id or material_id)
    session.add(job)
    session.commit()
    session.refresh(job)
    settings = Settings()
    job_id = job.id
    assert job_id is not None

    def session_factory():
        return Session(get_engine(settings))

    background_tasks.add_task(
        generate_flashcards_for_job,
        job_id,
        settings=settings,
        session_factory=session_factory,
    )
    return {"job_id": job_id, "status": "pending"}


@router.get("/flashcard-jobs/{job_id}")
def flashcard_job_status(
    job_id: int,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    job = session.get(FlashcardJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Flashcard job not found")
    return {
        "id": job.id,
        "status": job.status,
        "cards_created": job.cards_created,
        "error": job.error,
    }


@router.get("/courses/{course_id}/flashcards.anki", response_class=Response)
def export_anki(
    course_id: int,
    session: Session = Depends(get_session),
) -> Response:
    if session.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail="Course not found")
    cards = session.exec(
        select(Flashcard).where(Flashcard.course_id == course_id).order_by(Flashcard.id)
    ).all()
    from app.ai.flashcards import FlashcardDraft

    payload = to_anki_tsv(
        [
            FlashcardDraft(question=card.question, answer=card.answer, source=card.source)
            for card in cards
        ]
    )
    return Response(
        content=payload,
        media_type="text/tab-separated-values",
        headers={
            "Content-Disposition": f'attachment; filename="course-{course_id}-flashcards.tsv"'
        },
    )
