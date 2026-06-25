from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database.connection import get_db
from app.models.admin import Admin
from app.models.attendance import Attendance
from app.models.detection import Detection
from app.models.unknown_face import UnknownFace
from app.models.user import User
from app.utils.config import get_settings
from app.utils.templates import templates

router = APIRouter(tags=["Dashboard"])
settings = get_settings()


def _dashboard_context(request: Request, admin: Admin, page: str) -> dict:
    return {
        "request": request,
        "app_name": settings.app_name,
        "admin": admin,
        "active_page": page,
    }


@router.get("/")
async def root(request: Request, db: Session = Depends(get_db)):
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return RedirectResponse(url="/login", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/dashboard")
async def dashboard_home(request: Request, db: Session = Depends(get_db)):
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    total_users = db.scalar(select(func.count()).select_from(User)) or 0
    total_detections = db.scalar(select(func.count()).select_from(Detection)) or 0
    total_unknown = db.scalar(select(func.count()).select_from(UnknownFace)) or 0

    context = _dashboard_context(request, auth, "dashboard")
    context.update(
        {
            "stats": {
                "registered_users": total_users,
                "detections": total_detections,
                "unknown_faces": total_unknown,
            }
        }
    )
    return templates.TemplateResponse("dashboard/index.html", context)


@router.get("/dashboard/detections")
async def dashboard_detections(request: Request, db: Session = Depends(get_db)):
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    detections = db.scalars(
        select(Detection).order_by(Detection.timestamp.desc()).limit(50)
    ).all()

    context = _dashboard_context(request, auth, "detections")
    context["detections"] = detections
    return templates.TemplateResponse("dashboard/detections.html", context)


@router.get("/dashboard/users")
async def dashboard_users(
    request: Request,
    db: Session = Depends(get_db),
    registered: int | None = None,
):
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    users = db.scalars(select(User).order_by(User.registered_at.desc())).all()

    context = _dashboard_context(request, auth, "users")
    context["users"] = users
    context["registered_id"] = registered
    return templates.TemplateResponse("dashboard/users.html", context)


@router.get("/dashboard/attendance")
async def dashboard_attendance(request: Request, db: Session = Depends(get_db)):
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    records = db.scalars(
        select(Attendance).order_by(Attendance.detection_time.desc()).limit(100)
    ).all()

    context = _dashboard_context(request, auth, "attendance")
    context["records"] = records
    context["attendance_interval"] = settings.attendance_interval
    return templates.TemplateResponse("dashboard/attendance.html", context)
