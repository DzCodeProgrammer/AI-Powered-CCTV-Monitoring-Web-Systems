from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_admin_from_session
from app.database.connection import get_db
from app.services.auth_service import authenticate_admin
from app.utils.config import get_settings
from app.utils.templates import templates

router = APIRouter(tags=["Auth"])
settings = get_settings()


@router.get("/login")
async def login_page(request: Request, db: Session = Depends(get_db)):
    if get_admin_from_session(request, db):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "error": None,
        },
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = authenticate_admin(db, username.strip(), password)
    if not admin:
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "app_name": settings.app_name,
                "error": "Invalid username or password.",
                "username": username,
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    request.session["admin_id"] = admin.id
    request.session["admin_username"] = admin.username
    return RedirectResponse(url="/dashboard", status_code=303)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
