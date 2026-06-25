"""Verify Session 5: attendance logging and camera helpers."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from sqlalchemy import delete, select

from app.camera.manager import parse_camera_source
from app.database.connection import SessionLocal, init_db
from app.face_recognition.recognizer import STATUS_RECOGNIZED, FaceMatch
from app.models.attendance import Attendance
from app.services.attendance_service import has_recent_attendance, log_attendance
from app.utils.config import Settings, get_settings


def main() -> int:
    get_settings.cache_clear()
    settings = Settings(attendance_interval=60.0)
    init_db()

    if parse_camera_source("0") != 0:
        print("FAIL: webcam index parse")
        return 1
    if not str(parse_camera_source("rtsp://192.168.1.1/stream")).startswith("rtsp"):
        print("FAIL: rtsp source parse")
        return 1

    db = SessionLocal()
    try:
        db.execute(delete(Attendance).where(Attendance.person_name == "_Verify S5_"))
        db.commit()

        match = FaceMatch(
            name="_Verify S5_",
            status=STATUS_RECOGNIZED,
            confidence=0.91,
            user_id=None,
            bbox=(0, 0, 10, 10),
        )
        saved = log_attendance(db, settings, [match], camera_source="0")
        if len(saved) != 1:
            print("FAIL: first attendance not saved")
            return 1
        record = saved[0]
        if not record.id or record.person_name != "_Verify S5_":
            print("FAIL: attendance fields missing")
            return 1
        if record.camera_source != "0" or record.status != STATUS_RECOGNIZED:
            print("FAIL: attendance metadata incorrect")
            return 1

        if has_recent_attendance(db, "_Verify S5_", "0", settings.attendance_interval):
            pass
        else:
            print("FAIL: recent attendance should be detected")
            return 1

        saved_again = log_attendance(db, settings, [match], camera_source="0")
        if saved_again:
            print("FAIL: duplicate attendance should be suppressed")
            return 1

        count = db.scalar(
            select(Attendance).where(Attendance.person_name == "_Verify S5_")
        )
        if count is None:
            print("FAIL: attendance row missing")
            return 1

        db.execute(delete(Attendance).where(Attendance.person_name == "_Verify S5_"))
        db.commit()
    finally:
        db.close()

    print("Session 5 CCTV monitoring verification: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
