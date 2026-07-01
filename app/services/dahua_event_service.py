"""Process Dahua FaceDetection snapshots through the recognition pipeline."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

import cv2
import numpy as np

from app.database.connection import SessionLocal
from app.face_recognition.overlay import draw_face_boxes
from app.face_recognition.recognizer import STATUS_DETECTING, FaceMatch
from app.integrations.dahua.subscriber import run_subscriber_with_reconnect
from app.services.attendance_service import log_attendance
from app.services.detection_service import log_matches
from app.services.monitoring_service import is_monitoring_active
from app.services.recognition_service import get_recognizer
from app.utils.config import Settings, get_settings
from app.utils.logging import get_logger

logger = get_logger("dahua.processor")

_stop_event: asyncio.Event | None = None
_task: asyncio.Task | None = None
_processing_lock = asyncio.Lock()


@dataclass
class DahuaEventStatus:
    connected: bool = False
    last_event_at: datetime | None = None
    last_error: str | None = None
    events_processed: int = 0
    last_metadata: dict[str, str] = field(default_factory=dict)


_status = DahuaEventStatus()


def get_event_status() -> DahuaEventStatus:
    return _status


def event_capture_should_run(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return settings.event_capture_active


async def _on_connected() -> None:
    _status.connected = True
    _status.last_error = None


async def _on_disconnected() -> None:
    _status.connected = False


async def start_event_capture() -> None:
    global _stop_event, _task
    settings = get_settings()
    if not event_capture_should_run(settings):
        logger.info("Dahua event capture disabled (cctv_mode=%s)", settings.cctv_mode)
        return
    if _task and not _task.done():
        return

    _stop_event = asyncio.Event()
    _task = asyncio.create_task(
        run_subscriber_with_reconnect(
            settings,
            _on_snapshot,
            _stop_event,
            on_connected=_on_connected,
            on_disconnected=_on_disconnected,
        ),
        name="dahua-event-capture",
    )
    logger.info("Dahua event capture task started")


async def stop_event_capture() -> None:
    global _task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
    _stop_event = None
    _status.connected = False


async def _on_snapshot(jpeg_bytes: bytes, metadata: dict[str, str]) -> None:
    # Avoid YuNet/DeepFace lock contention while live monitor is running.
    if is_monitoring_active():
        return

    async with _processing_lock:
        _status.connected = True
        _status.last_event_at = datetime.now(timezone.utc)
        _status.last_metadata = dict(metadata)
        _status.last_error = None

        frame = _decode_jpeg(jpeg_bytes)
        if frame is None:
            _status.last_error = "Failed to decode JPEG snapshot"
            logger.warning("Dahua event: invalid JPEG (%s bytes)", len(jpeg_bytes))
            return

        settings = get_settings()
        camera_source = settings.dahua_event_camera_source

        try:
            recognizer = get_recognizer()
        except RuntimeError:
            _status.last_error = "Recognition not initialized"
            return

        try:
            annotated, matches = recognizer.process_snapshot(frame)
        except Exception as exc:
            _status.last_error = f"Event recognition failed: {exc}"
            logger.warning("Dahua event snapshot handler failed: %s", exc)
            return

        loggable = [m for m in matches if m.status != STATUS_DETECTING]
        if not loggable:
            logger.debug("Dahua event: no faces recognized in snapshot")
            return

        session = SessionLocal()
        try:
            log_matches(
                session,
                settings,
                annotated,
                loggable,
                camera_source=camera_source,
            )
            log_attendance(session, settings, loggable, camera_source=camera_source)
        finally:
            session.close()

        _status.events_processed += 1
        logger.info(
            "Dahua event processed: %s face(s), source=%s",
            len(loggable),
            camera_source,
        )


def _decode_jpeg(data: bytes) -> np.ndarray | None:
    if not data:
        return None
    arr = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None or frame.size == 0:
        return None
    return np.ascontiguousarray(frame)
