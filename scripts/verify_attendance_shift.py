"""Verify attendance shift windows (masuk/pulang WIB) and WA throttle logic."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")


def _utc_from_wib(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    from zoneinfo import ZoneInfo

    local = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("Asia/Jakarta"))
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def main() -> int:
    from app.services.attendance_shift import (
        current_shift,
        shift_label,
        should_notify_attendance_wa,
    )

    cases = [
        (_utc_from_wib(2026, 6, 26, 7, 0), "masuk"),
        (_utc_from_wib(2026, 6, 26, 12, 30), "masuk"),
        (_utc_from_wib(2026, 6, 26, 16, 59), "masuk"),
        (_utc_from_wib(2026, 6, 26, 17, 0), "pulang"),
        (_utc_from_wib(2026, 6, 26, 23, 0), "pulang"),
        (_utc_from_wib(2026, 6, 27, 6, 59), "pulang"),
    ]
    for at, expected in cases:
        got = current_shift(at)
        if got != expected:
            print(f"FAIL: current_shift at WIB-ish {at} expected {expected}, got {got}")
            return 1

    if shift_label("masuk") != "Masuk" or shift_label("pulang") != "Pulang":
        print("FAIL: shift_label")
        return 1

    from sqlalchemy import delete, select

    from app.database.connection import SessionLocal, init_db
    from app.models.attendance import Attendance
    from app.models.user import User

    init_db()
    db = SessionLocal()
    try:
        name = "_Verify Shift_"
        db.execute(delete(Attendance).where(Attendance.detected_name == name))
        db.execute(delete(User).where(User.full_name == name))
        db.commit()

        user = User(full_name=name, image_path="dataset/_verify_shift.jpg", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        at_masuk = _utc_from_wib(2026, 6, 26, 8, 0)
        db.add(
            Attendance(
                user_id=user.id,
                detected_name=name,
                detected_at=at_masuk,
                camera_source="test",
                status="Recognized",
                confidence=0.9,
            )
        )
        db.commit()

        ok1, shift1 = should_notify_attendance_wa(db, user.id, at_masuk)
        if not ok1 or shift1 != "masuk":
            print(f"FAIL: first masuk should notify, got ok={ok1} shift={shift1}")
            return 1

        at_masuk2 = _utc_from_wib(2026, 6, 26, 9, 0)
        db.add(
            Attendance(
                user_id=user.id,
                detected_name=name,
                detected_at=at_masuk2,
                camera_source="test",
                status="Recognized",
                confidence=0.88,
            )
        )
        db.commit()
        ok2, _ = should_notify_attendance_wa(db, user.id, at_masuk2)
        if ok2:
            print("FAIL: second masuk same window should not notify WA")
            return 1

        at_pulang = _utc_from_wib(2026, 6, 26, 18, 0)
        db.add(
            Attendance(
                user_id=user.id,
                detected_name=name,
                detected_at=at_pulang,
                camera_source="test",
                status="Recognized",
                confidence=0.87,
            )
        )
        db.commit()
        ok3, shift3 = should_notify_attendance_wa(db, user.id, at_pulang)
        if not ok3 or shift3 != "pulang":
            print(f"FAIL: first pulang should notify, got ok={ok3} shift={shift3}")
            return 1

        count = db.scalar(
            select(__import__("sqlalchemy").func.count())
            .select_from(Attendance)
            .where(Attendance.detected_name == name)
        )
        if count != 3:
            print(f"FAIL: expected 3 attendance rows in DB for shift test, got {count}")
            return 1
    finally:
        db.close()

    print("Attendance shift verification: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
