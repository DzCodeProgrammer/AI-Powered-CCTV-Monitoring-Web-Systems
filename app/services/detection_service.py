from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.face_recognition.recognizer import STATUS_UNKNOWN, FaceMatch
from app.database.errors import safe_commit
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
    image: np.ndarray,
    prefix: str,
    settings: Settings,
    subdir: str = "",
) -> str | None:
    screenshot_dir = Path(settings.screenshot_dir)
    if subdir:
        screenshot_dir = screenshot_dir / subdir
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = prefix.replace(" ", "_")
    file_path = screenshot_dir / f"{safe_name}_{timestamp}.jpg"
    if cv2.imwrite(str(file_path), image):
        if subdir:
            return f"{settings.screenshot_dir}/{subdir}/{file_path.name}".replace("\\", "/")
        return str(file_path).replace("\\", "/")
    return None


def _crop_face(frame: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = bbox
    height, width = frame.shape[:2]
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(width, x + w)
    y2 = min(height, y + h)
    return frame[y1:y2, x1:x2]


def log_matches(
    db: Session,
    settings: Settings,
    frame: np.ndarray,
    matches: list[FaceMatch],
    camera_source: str | None = None,
) -> None:
    source = camera_source or settings.camera_source
    committed = False

    for match in matches:
        log_key = f"{match.status}:{match.name}:{source}"
        if not _should_log(log_key, settings.detection_interval):
            continue

        if match.status == STATUS_UNKNOWN:
            face_crop = _crop_face(frame, match.bbox)
            screenshot_path = _save_screenshot(
                face_crop,
                "Unknown",
                settings,
                subdir="unknown",
            )
        else:
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
                    image_path=screenshot_path,
                    camera_source=source,
                    notes="Auto-detected unknown face",
                )
            )

        committed = True

    if committed:
        safe_commit(db, "log detection matches")
