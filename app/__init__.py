import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import auth, dashboard, health, monitoring, registration
from app.database.connection import SessionLocal, init_db
from app.services.auth_service import ensure_default_admin
from app.services.recognition_service import initialize_recognition
from app.utils.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    for folder in [settings.dataset_dir, settings.screenshot_dir, settings.log_dir, "database"]:
        os.makedirs(folder, exist_ok=True)
    init_db()
    db = SessionLocal()
    try:
        ensure_default_admin(db, settings)
        initialize_recognition(db, settings)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        max_age=settings.session_max_age,
        same_site="lax",
        https_only=False,
    )

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    os.makedirs(static_dir, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(registration.router)
    app.include_router(monitoring.router)

    return app
