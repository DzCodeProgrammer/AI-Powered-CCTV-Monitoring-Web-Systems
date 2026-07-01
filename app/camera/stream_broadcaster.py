"""Single background producer for low-latency MJPEG — one RTSP reader, many viewers."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

import cv2
import numpy as np

from app.camera.frames import make_status_frame
from app.camera.manager import CameraManager
from app.face_recognition.recognizer import RecognitionEvent
from app.utils.config import Settings, get_settings
from app.utils.logging import get_logger, log_exception

if TYPE_CHECKING:
    from app.face_recognition.recognizer import FaceRecognizer

logger = get_logger("stream")

MJPEG_BOUNDARY = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
AI_TICK_EVERY = 1


class LiveStreamBroadcaster:
    """Reads the camera once and shares the latest JPEG with all dashboard clients."""

    _lock = threading.Lock()
    _instance: LiveStreamBroadcaster | None = None

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._latest_jpeg: bytes | None = None
        self._latest_frame: np.ndarray | None = None
        self._frame_lock = threading.Lock()
        self._frame_ready = threading.Condition()
        self._camera_source: str | None = None
        self._on_recognition: Callable[[RecognitionEvent], None] | None = None
        self._connected = False
        self._last_error: str | None = None

    @classmethod
    def get(cls) -> LiveStreamBroadcaster:
        with cls._lock:
            if cls._instance is None:
                cls._instance = LiveStreamBroadcaster()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                cls._instance.stop()
                cls._instance = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def ensure_running(
        self,
        settings: Settings,
        recognizer: FaceRecognizer,
        camera_source: str,
        on_recognition: Callable[[RecognitionEvent], None] | None = None,
    ) -> None:
        with self._lock:
            self._on_recognition = on_recognition
            if self.is_running and self._camera_source == camera_source:
                return
            if self.is_running:
                self._stop.set()
                if self._thread is not None:
                    self._thread.join(timeout=3.0)
                self._stop.clear()
                CameraManager.reset()

            self._camera_source = camera_source
            self._latest_jpeg = None
            self._last_error = None
            self._thread = threading.Thread(
                target=self._producer_loop,
                args=(settings, recognizer, camera_source),
                name="live-stream-producer",
                daemon=True,
            )
            self._thread.start()
            logger.info("Live stream producer started for %s", camera_source)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        self._latest_jpeg = None
        with self._frame_lock:
            self._latest_frame = None
        self._camera_source = None
        self._connected = False
        CameraManager.reset()
        with self._frame_ready:
            self._frame_ready.notify_all()
        logger.info("Live stream producer stopped")

    def get_latest_frame(self) -> np.ndarray | None:
        """Latest annotated BGR frame for native desktop UI (no JPEG round-trip)."""
        with self._frame_lock:
            return self._latest_frame

    def _publish_frame(self, annotated: np.ndarray, jpeg: bytes | None) -> None:
        with self._frame_lock:
            self._latest_frame = annotated
        with self._frame_ready:
            if jpeg is not None:
                self._latest_jpeg = jpeg
            self._frame_ready.notify_all()

    def _producer_loop(
        self,
        settings: Settings,
        recognizer: FaceRecognizer,
        camera_source: str,
    ) -> None:
        tick = 0
        settings_tick = 0
        quality = int(settings.performance_profile["jpeg_quality"])
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        desktop_mode = settings.desktop_mode

        try:
            camera = CameraManager.get_instance(settings, recognizer, camera_source)
        except Exception as exc:
            log_exception("stream", "Could not open camera for stream producer", exc)
            self._connected = False
            self._last_error = f"Could not open camera: {exc}"
            return

        while not self._stop.is_set():
            if recognizer.is_shutdown:
                break

            try:
                settings_tick += 1
                if settings_tick % 120 == 0:
                    get_settings.cache_clear()
                    settings = get_settings()
                    quality = int(settings.performance_profile["jpeg_quality"])
                    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
                    desktop_mode = settings.desktop_mode

                frame = camera.read_frame()
                self._connected = camera.is_connected
                self._last_error = None if camera.is_connected else camera.last_error

                if frame is None:
                    annotated = camera.status_frame()
                else:
                    if desktop_mode:
                        self._publish_frame(recognizer.preview_stream_frame(frame), None)
                    tick += 1
                    run_ai = tick % AI_TICK_EVERY == 0
                    annotated, _ = recognizer.annotate_stream_frame(frame, run_ai=run_ai)

                if self._on_recognition is not None:
                    for event in recognizer.drain_recognition_events():
                        try:
                            self._on_recognition(event)
                        except Exception as exc:
                            log_exception("stream", "Recognition callback failed", exc)

                if desktop_mode:
                    self._publish_frame(annotated, None)
                else:
                    success, buffer = cv2.imencode(".jpg", annotated, encode_params)
                    jpeg_bytes = buffer.tobytes() if success else None
                    self._publish_frame(annotated, jpeg_bytes)

            except Exception as exc:
                if not self._stop.is_set():
                    log_exception("stream", "Stream producer tick failed", exc)
                fallback = make_status_frame("Stream error", "Retrying...")
                ok, buffer = cv2.imencode(".jpg", fallback, encode_params)
                jpeg_bytes = buffer.tobytes() if ok else None
                self._publish_frame(fallback, jpeg_bytes)
                time.sleep(0.2)
                continue

            if not desktop_mode:
                time.sleep(0.001)

    def iter_mjpeg(self) -> iter:
        """Yield multipart chunks; new clients get the latest frame immediately."""
        while not self._stop.is_set():
            with self._frame_ready:
                jpeg = self._latest_jpeg
                if jpeg is None:
                    self._frame_ready.wait(timeout=0.5)
                    jpeg = self._latest_jpeg
            if jpeg is None:
                placeholder = make_status_frame("Connecting to camera...", "Please wait")
                ok, buffer = cv2.imencode(
                    ".jpg",
                    placeholder,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 70],
                )
                if ok:
                    jpeg = buffer.tobytes()
                else:
                    time.sleep(0.1)
                    continue
            yield MJPEG_BOUNDARY + jpeg + b"\r\n"
            with self._frame_ready:
                self._frame_ready.wait(timeout=0.15)

    def iter_idle_mjpeg(self, settings: Settings, message: str, submessage: str = "") -> iter:
        quality = int(settings.performance_profile["jpeg_quality"])
        while not self._stop.is_set():
            frame = make_status_frame(message, submessage)
            ok, buffer = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), quality],
            )
            if ok:
                yield MJPEG_BOUNDARY + buffer.tobytes() + b"\r\n"
            time.sleep(1.0)
