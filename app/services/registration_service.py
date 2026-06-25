import io
import re
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.utils.config import Settings

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class RegistrationError(Exception):
    pass


def slugify_name(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name.strip(), flags=re.UNICODE)
    cleaned = re.sub(r"[\s_-]+", "_", cleaned)
    return cleaned.lower() or "person"


def validate_image_file(file: UploadFile, content: bytes) -> str:
    if not file.filename:
        raise RegistrationError("Image file is required.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise RegistrationError("Allowed formats: JPG, JPEG, PNG, WEBP.")

    if len(content) > MAX_UPLOAD_BYTES:
        raise RegistrationError("Image must be 5 MB or smaller.")

    try:
        image = Image.open(io.BytesIO(content))
        image.verify()
    except Exception as exc:
        raise RegistrationError("Invalid image file.") from exc

    return ext


def get_user_by_name(db: Session, name: str) -> User | None:
    return db.scalar(select(User).where(User.name == name))


def register_person(
    db: Session,
    settings: Settings,
    name: str,
    file: UploadFile,
    content: bytes,
) -> User:
    name = name.strip()
    if not name:
        raise RegistrationError("Person name is required.")
    if len(name) > 100:
        raise RegistrationError("Name must be 100 characters or fewer.")

    if get_user_by_name(db, name):
        raise RegistrationError(f"A person named '{name}' is already registered.")

    ext = validate_image_file(file, content)

    dataset_dir = Path(settings.dataset_dir)
    dataset_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{slugify_name(name)}_{timestamp}{ext}"
    file_path = dataset_dir / filename

    file_path.write_bytes(content)
    relative_path = f"{settings.dataset_dir}/{filename}".replace("\\", "/")

    user = User(
        name=name,
        image_path=relative_path,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
