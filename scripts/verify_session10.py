"""Verify Session 10: error handling and logging."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")


def main() -> int:
    from app.camera.frames import make_status_frame
    from app.camera.manager import CameraManager, MAX_CONSECUTIVE_FAILURES
    from app.database.errors import safe_commit
    from app.utils.config import get_settings
    from app.utils.logging import get_logger, log_exception, setup_logging

    settings = get_settings()
    log_dir = Path(settings.log_dir)
    setup_logging(log_dir)

    if not log_dir.is_dir():
        print("FAIL: logs directory missing")
        return 1

    log_exception("verify_session10", "Test error log entry")
    errors_log = log_dir / "errors.log"
    app_log = log_dir / "app.log"
    if not errors_log.is_file():
        print("FAIL: logs/errors.log not created")
        return 1
    if not app_log.is_file():
        print("FAIL: logs/app.log not created")
        return 1
    print(f"Log files OK: {app_log.name}, {errors_log.name}")

    frame = make_status_frame("Camera disconnected", "Reconnecting...")
    if frame is None or frame.size == 0:
        print("FAIL: status frame generation failed")
        return 1
    print("Camera status frame: OK")

    db = MagicMock()
    db.commit.side_effect = RuntimeError("simulated db failure")
    from sqlalchemy.exc import SQLAlchemyError

    db.commit.side_effect = SQLAlchemyError("simulated")
    if safe_commit(db, "test commit"):
        print("FAIL: safe_commit should return False on error")
        return 1
    print("Database safe_commit: OK")

    with patch("app.camera.manager.open_video_capture") as mock_open:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_open.return_value = mock_cap

        from app.face_recognition.embeddings import EmbeddingStore
        from app.face_recognition.recognizer import FaceRecognizer

        recognizer = FaceRecognizer(settings, EmbeddingStore(entries=[]))
        manager = CameraManager(settings, recognizer, camera_source="0")
        if manager.is_connected:
            print("FAIL: manager should report disconnected when open fails")
            return 1
        status = manager.status_frame()
        if status is None or status.size == 0:
            print("FAIL: disconnected manager should produce status frame")
            return 1
    print("Camera disconnect handling: OK")

    missing_logged = False

    import logging

    class _CaptureHandler(logging.Handler):
        messages: list[str] = []

        def emit(self, record: logging.LogRecord) -> None:
            self.messages.append(record.getMessage())

    capture = _CaptureHandler()
    logger = get_logger("face_recognition")
    logger.addHandler(capture)

    from app.face_recognition.embeddings import build_embeddings_from_db

    user = MagicMock()
    user.id = 99
    user.full_name = "Missing Person"
    user.image_path = "datasets/does_not_exist.jpg"
    user.is_active = True

    db2 = MagicMock()
    db2.scalars.return_value.all.return_value = [user]
    build_embeddings_from_db(db2, settings)
    missing_logged = any("Missing face image" in msg for msg in capture.messages)
    if not missing_logged:
        print("FAIL: missing face image should be logged")
        return 1
    print("Missing face image logging: OK")

    if MAX_CONSECUTIVE_FAILURES < 1:
        print("FAIL: invalid reconnect threshold")
        return 1

    print("Session 10 error handling verification: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
