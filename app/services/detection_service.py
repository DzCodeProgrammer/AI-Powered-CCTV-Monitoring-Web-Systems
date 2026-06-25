from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.face_recognition.recognizer import STATUS_UNKNOWN, FaceMatch
from app.models.detection import Detection
from app.models.unknown_face import UnknownFace
from app.utils.config import Settings

_last_logged: dict[str, float] = {}


def _should_log(key: str, interval: float) -> bool:
    now = time.time()
    last = _last_logged.get(key, 0.0)
    if now - last < interval:
        return False
    _last_logged[key] = now
    return True


def _save_screenshot(
    frame: np.ndarray,
    name: str,
    settings: Settings,
) -> str | None:
    screenshot_dir = Path(settings.screenshot_dir)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = name.replace(" ", "_")
    file_path = screenshot_dir / f"{safe_name}_{timestamp}.jpg"
    if cv2.imwrite(str(file_path), frame):
        return str(file_path).replace("\\", "/")
    return None


def log_matches(
    db: Session,
    settings: Settings,
    frame: np.ndarray,
    matches: list[FaceMatch],
    camera_source: str | None = None,
) -> None:
    source = camera_source or settings.camera_source
    for match in matches:
        log_key = f"{match.status}:{match.name}:{source}"
        if not _should_log(log_key, settings.detection_interval):
            continue

        screenshot_path = _save_screenshot(frame, match.name, settings)
        detection = Detection(
            user_id=match.user_id,
            name=match.name,
            status=match.status,
            confidence=match.confidence,
            screenshot_path=screenshot_path,
            camera_source=source,
        )
        db.add(detection)

        if match.status == STATUS_UNKNOWN and screenshot_path:
            db.add(
                UnknownFace(
                    screenshot_path=screenshot_path,
                    camera_source=source,
                    notes="Auto-detected unknown face",
                )
            )

    if matches:
        db.commit()
