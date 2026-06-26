from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database.connection import get_db
from app.database.errors import run_db_operation
from app.models.admin import Admin
from app.models.attendance import Attendance
from app.models.detection import Detection
from app.models.unknown_face import UnknownFace
from app.models.user import User
from app.services.dashboard_service import (
    AttendanceStats,
    DashboardStats,
    get_dashboard_stats,
    get_recent_activity,
)
from app.services.export_service import export_attendance_to_excel, fetch_attendance_records
from app.services.unknown_face_service import (
    count_unknown_faces,
    delete_all_unknown_faces,
    delete_unknown_face,
)
from app.services.user_service import delete_user
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


def _resolve_screenshot_path(stored_path: str) -> Path | None:
    path = Path(stored_path)
    if path.is_file():
        return path
    alt = Path.cwd() / stored_path
    if alt.is_file():
        return alt
    return None


@router.get("/")
async def root(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return RedirectResponse(url="/login", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/dashboard")
async def dashboard_home(request: Request, db: Session = Depends(get_db)):
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    stats = run_db_operation(
        db,
        "load dashboard stats",
        lambda: get_dashboard_stats(db),
        default=DashboardStats(
            registered_users=0,
            detections_today=0,
            unknown_detections_today=0,
            unknown_faces_total=0,
            attendance=AttendanceStats(0, 0, 0, 0),
        ),
    )
    recent_activity = run_db_operation(
        db,
        "load recent activity",
        lambda: get_recent_activity(db, limit=20),
        default=[],
    ) or []

    context = _dashboard_context(request, auth, "dashboard")
    context["stats"] = stats
    context["recent_activity"] = recent_activity
    context["db_error"] = request.query_params.get("error") == "server"
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

    users = db.scalars(select(User).order_by(User.created_at.desc())).all()

    context = _dashboard_context(request, auth, "users")
    context["users"] = users
    context["registered_id"] = registered
    context["deleted"] = request.query_params.get("deleted") == "1"
    context["delete_error"] = request.query_params.get("error") == "delete"
    return templates.TemplateResponse("dashboard/users.html", context)


@router.post("/dashboard/users/{user_id}/delete")
async def delete_registered_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    if not delete_user(db, user_id, settings):
        return RedirectResponse(url="/dashboard/users?error=delete", status_code=303)
    return RedirectResponse(url="/dashboard/users?deleted=1", status_code=303)


@router.get("/dashboard/attendance")
async def dashboard_attendance(
    request: Request,
    db: Session = Depends(get_db),
    exported: str | None = None,
):
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    records = db.scalars(
        select(Attendance).order_by(Attendance.detected_at.desc()).limit(100)
    ).all()

    context = _dashboard_context(request, auth, "attendance")
    context["records"] = records
    context["attendance_interval"] = settings.attendance_interval
    context["total_records"] = len(records)
    context["export_success"] = exported == "1"
    return templates.TemplateResponse("dashboard/attendance.html", context)


@router.get("/dashboard/attendance/export")
async def export_attendance_excel(
    request: Request,
    db: Session = Depends(get_db),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> Response:
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    content, filename = export_attendance_to_excel(db, start=start_date, end=end_date)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/dashboard/attendance/export/preview")
async def attendance_export_preview(
    request: Request,
    db: Session = Depends(get_db),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
):
    """Export page with date filters and record count."""
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    records = fetch_attendance_records(db, start=start_date, end=end_date, limit=10_000)
    context = _dashboard_context(request, auth, "attendance")
    context["records"] = records[:100]
    context["attendance_interval"] = settings.attendance_interval
    context["total_records"] = len(records)
    context["start_date"] = start_date.isoformat() if start_date else ""
    context["end_date"] = end_date.isoformat() if end_date else ""
    context["export_mode"] = True
    return templates.TemplateResponse("dashboard/attendance_export.html", context)


@router.get("/dashboard/unknown-faces")
async def unknown_faces_gallery(request: Request, db: Session = Depends(get_db)):
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    faces = db.scalars(
        select(UnknownFace).order_by(UnknownFace.detected_at.desc()).limit(60)
    ).all()

    context = _dashboard_context(request, auth, "unknown_faces")
    context["faces"] = faces
    context["total"] = count_unknown_faces(db)
    context["deleted"] = request.query_params.get("deleted") == "1"
    context["deleted_all"] = request.query_params.get("deleted_all") == "1"
    context["delete_error"] = request.query_params.get("error") == "delete"
    return templates.TemplateResponse("dashboard/unknown_faces.html", context)


@router.post("/dashboard/unknown-faces/{face_id}/delete")
async def delete_unknown_face_item(
    face_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    if not delete_unknown_face(db, face_id):
        return RedirectResponse(
            url="/dashboard/unknown-faces?error=delete",
            status_code=303,
        )
    return RedirectResponse(url="/dashboard/unknown-faces?deleted=1", status_code=303)


@router.post("/dashboard/unknown-faces/delete-all")
async def delete_all_unknown_face_items(
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    removed = delete_all_unknown_faces(db)
    if removed == 0:
        return RedirectResponse(url="/dashboard/unknown-faces", status_code=303)
    return RedirectResponse(url="/dashboard/unknown-faces?deleted_all=1", status_code=303)


@router.get("/dashboard/unknown-faces/{face_id}/image")
async def unknown_face_image(
    face_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    face = db.get(UnknownFace, face_id)
    if not face:
        return RedirectResponse(url="/dashboard/unknown-faces", status_code=303)

    file_path = _resolve_screenshot_path(face.image_path)
    if not file_path:
        return RedirectResponse(url="/dashboard/unknown-faces", status_code=303)

    return FileResponse(file_path)
