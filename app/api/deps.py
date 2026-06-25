from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.models.admin import Admin


def get_session_admin_id(request: Request) -> int | None:
    admin_id = request.session.get("admin_id")
    if isinstance(admin_id, int):
        return admin_id
    if isinstance(admin_id, str) and admin_id.isdigit():
        return int(admin_id)
    return None


def get_admin_from_session(request: Request, db: Session) -> Admin | None:
    admin_id = get_session_admin_id(request)
    if not admin_id:
        return None
    admin = db.get(Admin, admin_id)
    if not admin or not admin.is_active:
        return None
    return admin


def require_admin(request: Request, db: Session) -> Admin | RedirectResponse:
    admin = get_admin_from_session(request, db)
    if not admin:
        return RedirectResponse(url="/login", status_code=303)
    return admin
