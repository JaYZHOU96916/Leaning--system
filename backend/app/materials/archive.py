import tempfile
import uuid
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from sqlmodel import Session, select

from app.models import Material


def build_course_zip(session: Session, course_id: int, *, materials_root: Path) -> Path:
    materials = session.exec(
        select(Material)
        .where(Material.course_id == course_id)
        .order_by(Material.week, Material.category, Material.name)
    ).all()
    materials_root.parent.mkdir(parents=True, exist_ok=True)
    archive_dir = Path(tempfile.mkdtemp(prefix="academic-os-zip-", dir=materials_root.parent))
    archive_path = archive_dir / f"course-{course_id}-{uuid.uuid4().hex}.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for material in materials:
            if not material.local_path:
                continue
            source = Path(material.local_path)
            if not source.is_file():
                continue
            arcname = (
                Path(material.week or "Unsorted")
                / (material.category or "other")
                / material.name
            )
            archive.write(source, arcname.as_posix())
    return archive_path
