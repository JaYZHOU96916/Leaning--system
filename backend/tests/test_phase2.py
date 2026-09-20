from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

from app.ai.flashcards import (
    FlashcardDraft,
    LLMFlashcardExtractor,
    parse_flashcard_payload,
    to_anki_tsv,
)
from app.db import create_db_and_tables
from app.materials.archive import build_course_zip
from app.materials.sync import MaterialInput, MaterialSyncService
from app.models import Course, Material
from sqlmodel import Session, create_engine, select


def make_engine(tmp_path: Path):
    return create_engine(
        f"sqlite:///{tmp_path / 'phase2.db'}",
        connect_args={"check_same_thread": False},
    )


def test_material_sha256_dedup_and_remote_timestamp(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    create_db_and_tables(engine)
    root = tmp_path / "materials"
    updated = datetime(2026, 9, 20, 10, tzinfo=UTC)
    with Session(engine) as session:
        course = Course(canvas_id=10, name="Data Mining")
        session.add(course)
        session.commit()
        session.refresh(course)
        service = MaterialSyncService()
        item = MaterialInput(
            canvas_file_id=20,
            course_id=course.id,
            name="Week 01 Slides.pdf",
            remote_updated_at=updated,
            module_name="Week 1 - Introduction",
        )
        first = service.ingest_bytes(session, course, item, b"same bytes", root_dir=root)
        second = service.ingest_bytes(session, course, item, b"same bytes", root_dir=root)
        assert first.created == 1
        assert second.skipped == 1
        assert (root / "Data Mining" / "Week 01" / "readings" / "Week 01 Slides.pdf").is_file()

        duplicate_item = MaterialInput(
            canvas_file_id=21,
            course_id=course.id,
            name="renamed.pdf",
            remote_updated_at=updated,
            module_name="Week 1 - Introduction",
        )
        duplicate = service.ingest_bytes(
            session,
            course,
            duplicate_item,
            b"same bytes",
            root_dir=root,
        )
        assert duplicate.deduplicated == 1
        materials = session.exec(select(Material).where(Material.course_id == course.id)).all()
        assert len(materials) == 2
        assert materials[0].local_path == materials[1].local_path
        archive_path = build_course_zip(session, course.id, materials_root=root)
        with ZipFile(archive_path) as archive:
            assert "Week 01/readings/Week 01 Slides.pdf" in archive.namelist()


async def test_course_modules_and_files_sync_to_week_category_tree(tmp_path: Path) -> None:
    class FakeCanvasClient:
        async def get_all(self, url: str, **kwargs):
            if url.endswith("/modules"):
                return [
                    {
                        "id": 300,
                        "name": "Week 2 - Joins",
                        "items": [{"type": "File", "content_id": 400}],
                    }
                ]
            return [
                {
                    "id": 400,
                    "display_name": "joins.pdf",
                    "updated_at": "2026-09-20T10:00:00Z",
                    "url": "https://canvas.test/files/400",
                    "content-type": "application/pdf",
                }
            ]

        async def download_to_path(self, url: str, destination: Path) -> int:
            destination.write_bytes(b"joins material")
            return len(b"joins material")

    engine = make_engine(tmp_path)
    create_db_and_tables(engine)
    with Session(engine) as session:
        course = Course(canvas_id=40, name="Database Systems")
        session.add(course)
        session.commit()
        session.refresh(course)
        result = await MaterialSyncService(FakeCanvasClient()).sync_course(
            session,
            course,
            root_dir=tmp_path / "materials",
        )
        material = session.exec(select(Material)).one()

    assert result.created == 1
    assert material.week == "Week 02"
    assert material.category == "readings"
    assert Path(material.local_path or "").is_file()


async def test_flashcard_parser_deduplicates_and_exports_anki() -> None:
    async def fake_llm(prompt: str) -> str:
        assert "MATERIAL" in prompt
        return (
            '{"cards": [{"question": "What is ETL?", '
            '"answer": "Extract, transform, load."}, '
            '{"question": "What is ETL?", '
            '"answer": "Extract, transform, load."}]}'
        )

    cards = await LLMFlashcardExtractor(fake_llm).extract(
        "ETL is a data pipeline.",
        source="week1.pdf",
    )
    assert cards == [
        FlashcardDraft(
            question="What is ETL?",
            answer="Extract, transform, load.",
            source="week1.pdf",
        )
    ]
    assert to_anki_tsv(cards) == "What is ETL?\tExtract, transform, load.\n"


def test_flashcard_payload_accepts_code_fences() -> None:
    cards = parse_flashcard_payload(
        '```json\n{"cards":[{"question":"Q","answer":"A"}]}\n```',
        source="notes.md",
    )
    assert cards[0].source == "notes.md"
