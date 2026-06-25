from __future__ import annotations

import threading
import time
from typing import Any

import cv2
import numpy as np

from app.face_recognition.recognizer import FaceMatch, FaceRecognizer
from app.utils.config import Settings


def parse_camera_source(source: str) -> Any:
    source = source.strip()
    if source.isdigit():
        return int(source)
    return source


def open_video_capture(source: Any) -> cv2.VideoCapture:
    if isinstance(source, str) and source.lower().startswith("rtsp"):
        capture = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
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
        self._capture = open_video_capture(self._source)
        if not self._capture.isOpened():
            raise RuntimeError(f"Could not open camera source: {self.camera_source}")

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

    def read_frame(self) -> np.ndarray | None:
        with self._capture_lock:
            success, frame = self._capture.read()
        if not success:
            return None
        return frame

    def read_annotated(self) -> tuple[np.ndarray | None, list[FaceMatch]]:
        frame = self.read_frame()
        if frame is None:
            return None, []
        return self.recognizer.process_frame(frame)

    def release(self) -> None:
        with self._capture_lock:
            if self._capture.isOpened():
                self._capture.release()

    def generate_mjpeg(self, on_frame=None):
        while True:
            annotated, matches = self.read_annotated()
            if annotated is None:
                time.sleep(0.5)
                continue
            if on_frame is not None:
                on_frame(annotated, matches)
            success, buffer = cv2.imencode(".jpg", annotated)
            if not success:
                continue
            frame_bytes = buffer.tobytes()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
            time.sleep(0.03)
