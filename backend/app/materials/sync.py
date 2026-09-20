import hashlib
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.canvas.client import CanvasClient
from app.models import Course, Material
from app.sync.assignments import parse_canvas_datetime


def safe_component(value: str, fallback: str = "untitled") -> str:
    cleaned = re.sub(r"[^\w\-. ]+", "_", value, flags=re.UNICODE).strip(" .")
    return cleaned[:120] or fallback


def week_from_module(module_name: str | None) -> str:
    if not module_name:
        return "Unsorted"
    match = re.search(r"\bweek\s*[-_ ]?\s*(\d+)\b", module_name, flags=re.IGNORECASE)
    if match:
        return f"Week {int(match.group(1)):02d}"
    return safe_component(module_name, "Unsorted")


def category_for_filename(name: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix in {".ppt", ".pptx", ".key"}:
        return "slides"
    if suffix in {".pdf", ".doc", ".docx", ".txt", ".md", ".html"}:
        return "readings"
    if suffix in {".py", ".ipynb", ".js", ".ts", ".java", ".c", ".cpp"}:
        return "code"
    if suffix in {".zip", ".tar", ".gz", ".7z"}:
        return "archives"
    return "other"


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


@dataclass(frozen=True)
class MaterialInput:
    canvas_file_id: int
    course_id: int
    name: str
    content_type: str | None = None
    remote_updated_at: datetime | None = None
    download_url: str | None = None
    module_id: int | None = None
    module_name: str | None = None
    remote_path: str | None = None


@dataclass(frozen=True)
class MaterialSyncResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    deduplicated: int = 0


class MaterialSyncService:
    def __init__(self, client: CanvasClient | None = None):
        self.client = client

    def _target_path(self, root_dir: Path, course: Course, item: MaterialInput) -> Path:
        week = week_from_module(item.module_name)
        category = category_for_filename(item.name)
        return (
            root_dir
            / safe_component(course.name, f"course-{course.canvas_id}")
            / safe_component(week)
            / category
            / safe_component(item.name)
        )

    def ingest_bytes(
        self,
        session: Session,
        course: Course,
        item: MaterialInput,
        content: bytes,
        *,
        root_dir: Path,
    ) -> MaterialSyncResult:
        if course.id is None or course.id != item.course_id:
            raise ValueError("Material course_id must match a persisted Course")
        now = datetime.now(UTC)
        existing = session.exec(
            select(Material).where(Material.canvas_file_id == item.canvas_file_id)
        ).first()
        remote_updated_at = item.remote_updated_at
        if (
            existing is not None
            and remote_updated_at is not None
            and existing.remote_updated_at is not None
            and _as_utc(remote_updated_at) <= _as_utc(existing.remote_updated_at)
            and existing.local_path
            and Path(existing.local_path).is_file()
        ):
            return MaterialSyncResult(skipped=1)

        digest = sha256_bytes(content)
        duplicate = session.exec(
            select(Material)
            .where(Material.course_id == item.course_id)
            .where(Material.sha256 == digest)
        ).first()
        target = self._target_path(root_dir, course, item)
        if duplicate is not None and duplicate.local_path and Path(duplicate.local_path).is_file():
            local_path = duplicate.local_path
            deduplicated = 1
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.{digest}.part")
            temporary.write_bytes(content)
            os.replace(temporary, target)
            local_path = str(target)
            deduplicated = 0

        values: dict[str, Any] = {
            "canvas_file_id": item.canvas_file_id,
            "course_id": item.course_id,
            "name": item.name,
            "local_path": local_path,
            "sha256": digest,
            "remote_updated_at": remote_updated_at,
            "content_type": item.content_type,
            "size_bytes": len(content),
            "canvas_module_id": item.module_id,
            "remote_path": item.remote_path,
            "week": week_from_module(item.module_name),
            "category": category_for_filename(item.name),
            "download_url": item.download_url,
            "updated_at": now,
        }
        if existing is None:
            session.add(Material(**values))
            result = MaterialSyncResult(created=1, deduplicated=deduplicated)
        else:
            for key, value in values.items():
                setattr(existing, key, value)
            result = MaterialSyncResult(updated=1, deduplicated=deduplicated)
        session.commit()
        return result

    @staticmethod
    def _module_file_map(modules: list[dict[str, Any]]) -> dict[int, tuple[int | None, str | None]]:
        mapping: dict[int, tuple[int | None, str | None]] = {}
        for module in modules:
            module_id = module.get("id")
            module_name = module.get("name")
            for item in module.get("items") or []:
                if item.get("type") == "File" and item.get("content_id") is not None:
                    mapping[int(item["content_id"])] = (module_id, module_name)
        return mapping

    async def sync_course(
        self,
        session: Session,
        course: Course,
        *,
        root_dir: Path,
    ) -> MaterialSyncResult:
        if self.client is None:
            raise ValueError("CanvasClient is required for remote material sync")
        modules = await self.client.get_all(
            f"/courses/{course.canvas_id}/modules",
            params={"include[]": "items", "per_page": 100},
        )
        files = await self.client.get_all(
            f"/courses/{course.canvas_id}/files",
            params={"per_page": 100, "sort": "updated_at"},
        )
        module_map = self._module_file_map(
            [module for module in modules if isinstance(module, dict)]
        )
        result = MaterialSyncResult()
        for file_payload in files:
            if not isinstance(file_payload, dict) or file_payload.get("id") is None:
                continue
            module_id, module_name = module_map.get(int(file_payload["id"]), (None, None))
            item = MaterialInput(
                canvas_file_id=int(file_payload["id"]),
                course_id=course.id,
                name=str(
                    file_payload.get("display_name")
                    or file_payload.get("filename")
                    or file_payload["id"]
                ),
                content_type=file_payload.get("content-type"),
                remote_updated_at=parse_canvas_datetime(file_payload.get("updated_at")),
                download_url=file_payload.get("url"),
                module_id=int(module_id) if module_id is not None else None,
                module_name=module_name,
                remote_path=file_payload.get("full_name"),
            )
            existing = session.exec(
                select(Material).where(Material.canvas_file_id == item.canvas_file_id)
            ).first()
            if (
                existing is not None
                and item.remote_updated_at is not None
                and existing.remote_updated_at is not None
                and _as_utc(item.remote_updated_at) <= _as_utc(existing.remote_updated_at)
                and existing.local_path
                and Path(existing.local_path).is_file()
            ):
                result = MaterialSyncResult(
                    created=result.created,
                    updated=result.updated,
                    skipped=result.skipped + 1,
                    deduplicated=result.deduplicated,
                )
                continue
            if not item.download_url:
                continue
            target = self._target_path(root_dir, course, item)
            temporary = target.with_name(f".{target.name}.download.part")
            target.parent.mkdir(parents=True, exist_ok=True)
            await self.client.download_to_path(item.download_url, temporary)
            content = temporary.read_bytes()
            temporary.unlink(missing_ok=True)
            item_result = self.ingest_bytes(
                session,
                course,
                item,
                content,
                root_dir=root_dir,
            )
            result = MaterialSyncResult(
                created=result.created + item_result.created,
                updated=result.updated + item_result.updated,
                skipped=result.skipped + item_result.skipped,
                deduplicated=result.deduplicated + item_result.deduplicated,
            )
        return result
