"""Unknown face gallery — delete records and image files."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database.errors import safe_commit
from app.models.unknown_face import UnknownFace
from app.utils.logging import get_logger

logger = get_logger("unknown_faces")


def _resolve_image_path(stored_path: str) -> Path | None:
    path = Path(stored_path)
    if path.is_file():
        return path
    alt = Path.cwd() / stored_path
    if alt.is_file():
        return alt
    return None


def _remove_image_file(stored_path: str) -> None:
    file_path = _resolve_image_path(stored_path)
    if file_path is None:
        return
    try:
        file_path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Could not delete image %s: %s", stored_path, exc)


def delete_unknown_face(db: Session, face_id: int) -> bool:
    face = db.get(UnknownFace, face_id)
    if face is None:
        return False

    image_path = face.image_path
    db.delete(face)
    if not safe_commit(db, f"delete unknown face {face_id}"):
        return False

    _remove_image_file(image_path)
    return True


def delete_all_unknown_faces(db: Session) -> int:
    faces = list(db.scalars(select(UnknownFace)).all())
    if not faces:
        return 0

    image_paths = [face.image_path for face in faces]
    db.execute(delete(UnknownFace))
    if not safe_commit(db, "delete all unknown faces"):
        return 0

    for path in image_paths:
        _remove_image_file(path)
    return len(image_paths)


def count_unknown_faces(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(UnknownFace)) or 0
