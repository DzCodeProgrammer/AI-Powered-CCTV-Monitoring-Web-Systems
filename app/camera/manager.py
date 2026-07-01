from __future__ import annotations

import sys
import threading
import time
from typing import Any

import cv2
import numpy as np

from app.camera.frames import make_status_frame
from app.face_recognition.recognizer import FaceMatch, FaceRecognizer
from app.utils.config import Settings
from app.utils.logging import get_logger, log_exception

logger = get_logger("camera")

MAX_CONSECUTIVE_FAILURES = 5
RECONNECT_INTERVAL_SECONDS = 3.0


def parse_camera_source(source: str) -> Any:
    source = source.strip()
    if source.isdigit():
        return int(source)
    return source


def open_video_capture(source: Any) -> cv2.VideoCapture:
    if isinstance(source, str) and source.lower().startswith("rtsp"):
        capture = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        # Low-latency RTSP (FFmpeg options via OpenCV)
        try:
            capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000)
            capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000)
        except Exception:
            pass
    elif isinstance(source, int) or (isinstance(source, str) and source.strip().isdigit()):
        index = int(source)
        if sys.platform == "win32":
            capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        else:
            capture = cv2.VideoCapture(index)
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        capture.set(cv2.CAP_PROP_FPS, 30)
    else:
        capture = cv2.VideoCapture(source)
    return capture


class CameraManager:
    _instance: "CameraManager | None" = None
    _lock = threading.Lock()

    def __init__(
        self,
        settings: Settings,
        recognizer: FaceRecognizer,
        camera_source: str | None = None,
    ) -> None:
        self.settings = settings
        self.recognizer = recognizer
        self._capture_lock = threading.Lock()
        self.camera_source = camera_source or settings.camera_source
        self._source = parse_camera_source(self.camera_source)
        self._capture: cv2.VideoCapture | None = None
        self._connected = False
        self._consecutive_failures = 0
        self._last_reconnect_attempt = 0.0
        self._disconnect_logged = False
        self._last_error: str | None = None
        self._open_capture()

    def _open_capture(self) -> bool:
        with self._capture_lock:
            if self._capture is not None and self._capture.isOpened():
                self._capture.release()
            self._capture = open_video_capture(self._source)
            if self._capture.isOpened():
                self._connected = True
                self._consecutive_failures = 0
                self._disconnect_logged = False
                self._last_error = None
                logger.info("Camera opened: %s", self.camera_source)
                return True

            self._connected = False
            self._last_error = f"Could not open camera source: {self.camera_source}"
            log_exception("camera", self._last_error)
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @classmethod
    def get_instance(
        cls,
        settings: Settings,
        recognizer: FaceRecognizer,
        camera_source: str | None = None,
    ) -> "CameraManager":
        with cls._lock:
            source = camera_source or (
                cls._instance.camera_source if cls._instance else settings.camera_source
            )
            if cls._instance is None or cls._instance.camera_source != source:
                if cls._instance is not None:
                    cls._instance.release()
                cls._instance = CameraManager(settings, recognizer, source)
            else:
                cls._instance.recognizer = recognizer
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                cls._instance.release()
                cls._instance = None

    @classmethod
    def switch_source(
        cls,
        settings: Settings,
        recognizer: FaceRecognizer,
        camera_source: str,
    ) -> "CameraManager":
        cls.reset()
        return cls.get_instance(settings, recognizer, camera_source)

    def _maybe_reconnect(self) -> None:
        now = time.time()
        if now - self._last_reconnect_attempt < RECONNECT_INTERVAL_SECONDS:
            return
        self._last_reconnect_attempt = now
        logger.info("Attempting camera reconnect: %s", self.camera_source)
        if self._open_capture():
            logger.info("Camera reconnected: %s", self.camera_source)

    def read_frame(self) -> np.ndarray | None:
        with self._capture_lock:
            if self._capture is None or not self._capture.isOpened():
                self._connected = False
            else:
                is_rtsp = isinstance(self._source, str) and self._source.lower().startswith(
                    "rtsp"
                )
                frame = self._read_capture_frame(flush_buffer=is_rtsp)
                if frame is not None:
                    self._consecutive_failures = 0
                    self._connected = True
                    self._disconnect_logged = False
                    return frame
                self._consecutive_failures += 1

        if self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            if not self._disconnect_logged:
                self._connected = False
                self._last_error = "Camera disconnected — no frames received"
                log_exception("camera", self._last_error)
                self._disconnect_logged = True
            self._maybe_reconnect()
        return None

    def _read_capture_frame(self, flush_buffer: bool = False) -> np.ndarray | None:
        if self._capture is None:
            return None
        if flush_buffer:
            for _ in range(8):
                if not self._capture.grab():
                    break
            success, frame = self._capture.retrieve()
            if success and frame is not None:
                return frame
            return None
        success, frame = self._capture.read()
        if success and frame is not None:
            return frame
        return None

    def read_annotated(self) -> tuple[np.ndarray | None, list[FaceMatch]]:
        frame = self.read_frame()
        if frame is None:
            return None, []
        try:
            return self.recognizer.process_frame(frame)
        except Exception as exc:
            log_exception("camera", "Frame processing failed", exc)
            return None, []

    def status_frame(self) -> np.ndarray:
        if self._connected:
            return make_status_frame("Camera connected", "Waiting for frames...")
        if self._last_error:
            return make_status_frame("Camera unavailable", self._last_error)
        return make_status_frame(
            "Camera disconnected",
            "Reconnecting...",
        )

    def release(self) -> None:
        with self._capture_lock:
            if self._capture is not None and self._capture.isOpened():
                self._capture.release()
            self._capture = None
            self._connected = False

    def generate_mjpeg(self, on_recognition=None):
        while True:
            annotated, matches = self.read_annotated()
            if on_recognition is not None:
                for event in self.recognizer.drain_recognition_events():
                    try:
                        on_recognition(event)
                    except Exception as exc:
                        log_exception("camera", "Recognition callback failed", exc)

            if annotated is None:
                annotated = self.status_frame()
                matches = []

            success, buffer = cv2.imencode(
                ".jpg",
                annotated,
                [int(cv2.IMWRITE_JPEG_QUALITY), int(self.settings.performance_profile["jpeg_quality"])],
            )
            if not success:
                time.sleep(0.5)
                continue
            frame_bytes = buffer.tobytes()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
            time.sleep(0.02 if self._connected else 0.5)
