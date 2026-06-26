from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.utils.config import get_settings
from app.utils.logging import log_exception

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = "error"
        log_exception("database", "Health check database query failed", exc)

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "app": settings.app_name,
        "environment": settings.app_env,
        "database": db_status,
        "db_driver": settings.db_driver,
        "db_host": settings.db_host,
        "db_name": settings.db_name,
        "camera_mode": settings.camera_mode_label,
        "camera_source": settings.safe_camera_display,
    }
