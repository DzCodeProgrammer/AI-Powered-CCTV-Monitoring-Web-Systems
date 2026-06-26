from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.errors import safe_commit
from app.face_recognition.recognizer import STATUS_RECOGNIZED, FaceMatch
from app.models.attendance import Attendance
from app.utils.config import Settings


def has_recent_attendance(
    db: Session,
    person_name: str,
    camera_source: str,
    interval_seconds: float,
) -> bool:
    cutoff = datetime.utcnow() - timedelta(seconds=interval_seconds)
    existing = db.scalar(
        select(Attendance)
        .where(
            Attendance.detected_name == person_name,
            Attendance.camera_source == camera_source,
            Attendance.detected_at >= cutoff,
        )
        .order_by(Attendance.detected_at.desc())
        .limit(1)
    )
    return existing is not None


def log_attendance(
    db: Session,
    settings: Settings,
    matches: list[FaceMatch],
    camera_source: str,
) -> list[Attendance]:
    saved: list[Attendance] = []

    for match in matches:
        if has_recent_attendance(
            db,
            match.name,
            camera_source,
            settings.attendance_interval,
        ):
            continue

        record = Attendance(
            detected_name=match.name,
            user_id=match.user_id,
            detected_at=datetime.utcnow(),
            camera_source=camera_source,
            status=match.status,
            confidence=match.confidence,
        )
        db.add(record)
        saved.append(record)

    if saved:
        if safe_commit(db, "log attendance"):
            for record in saved:
                db.refresh(record)

    return saved
