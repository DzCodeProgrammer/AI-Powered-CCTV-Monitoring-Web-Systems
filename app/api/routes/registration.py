from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database.connection import get_db
from app.utils.logging import log_exception
from app.services.recognition_service import rebuild_embeddings
from app.services.registration_service import RegistrationError, register_person
from app.utils.config import get_settings
from app.utils.templates import templates

router = APIRouter(tags=["Registration"])
settings = get_settings()


@router.get("/dashboard/register")
async def register_page(request: Request, db: Session = Depends(get_db)):
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    return templates.TemplateResponse(
        "dashboard/register.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "admin": auth,
            "active_page": "register",
            "error": None,
            "success": None,
            "name": "",
        },
    )


@router.post("/dashboard/register")
async def register_submit(
    request: Request,
    name: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    context = {
        "request": request,
        "app_name": settings.app_name,
        "admin": auth,
        "active_page": "register",
        "error": None,
        "success": None,
        "name": name.strip(),
    }

    try:
        content = await image.read()
        user = register_person(db, settings, name, image, content)
        rebuild_embeddings(db, settings)
        return RedirectResponse(
            url=f"/dashboard/users?registered={user.id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except RegistrationError as exc:
        context["error"] = str(exc)
        return templates.TemplateResponse(
            "dashboard/register.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as exc:
        log_exception("registration", "Registration failed", exc)
        context["error"] = "Registration failed. Please try again."
        return templates.TemplateResponse(
            "dashboard/register.html",
            context,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.get("/dashboard/datasets/{filename}")
async def serve_dataset_image(
    filename: str,
    request: Request,
    db: Session = Depends(get_db),
):
    auth = require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    safe_name = filename.replace("\\", "/").split("/")[-1]
    file_path = Path(settings.dataset_dir) / safe_name
    if not file_path.is_file():
        return RedirectResponse(url="/dashboard/users", status_code=303)

    return FileResponse(file_path)
