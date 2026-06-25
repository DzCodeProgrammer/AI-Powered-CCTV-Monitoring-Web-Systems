from datetime import datetime

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin import Admin
from app.utils.config import Settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def get_admin_by_username(db: Session, username: str) -> Admin | None:
    return db.scalar(select(Admin).where(Admin.username == username))


def authenticate_admin(db: Session, username: str, password: str) -> Admin | None:
    admin = get_admin_by_username(db, username)
    if not admin or not admin.is_active:
        return None
    if not verify_password(password, admin.password_hash):
        return None
    admin.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(admin)
    return admin


def create_admin(db: Session, username: str, password: str) -> Admin:
    admin = Admin(
        username=username,
        password_hash=hash_password(password),
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def ensure_default_admin(db: Session, settings: Settings) -> None:
    if not settings.admin_username or not settings.admin_password:
        return
    existing = get_admin_by_username(db, settings.admin_username)
    if existing:
        return
    create_admin(db, settings.admin_username, settings.admin_password)
