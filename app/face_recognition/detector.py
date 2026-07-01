from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from app.face_recognition.pipeline_lock import AI_PIPELINE_LOCK
from app.utils.config import Settings
from app.utils.logging import get_logger

logger = get_logger("face_recognition")

YUNET_MODEL_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
YUNET_MODEL_PATH = Path("models") / "face_detection_yunet_2023mar.onnx"


def _resolve_cascade_path(filename: str) -> str:
    """Locate an OpenCV Haar cascade, resilient to PyInstaller bundling.

    In a frozen build `cv2.data.haarcascades` may point to a folder that was
    not collected, so also probe common bundle locations.
    """
    candidates: list[Path] = []

    cv2_data = getattr(getattr(cv2, "data", None), "haarcascades", None)
    if cv2_data:
        candidates.append(Path(cv2_data) / filename)

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base = Path(meipass)
        candidates.append(base / "cv2" / "data" / filename)
        candidates.append(base / "data" / filename)

    candidates.append(Path(cv2.__file__).resolve().parent / "data" / filename)

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    # Fall back to the cv2-reported path so the caller reports a useful error.
    return str(candidates[0]) if candidates else filename


def ensure_yunet_model() -> Path:
    if YUNET_MODEL_PATH.is_file():
        return YUNET_MODEL_PATH
    YUNET_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading YuNet face model to %s", YUNET_MODEL_PATH)
    urllib.request.urlretrieve(YUNET_MODEL_URL, YUNET_MODEL_PATH)
    return YUNET_MODEL_PATH


class FaceDetector:
    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or Settings()
        self._min_size = settings.face_min_size
        self._low_light = settings.detection_low_light
        self._backend = settings.face_detector
        self._yunet_score = settings.yunet_score_threshold
        self._yunet: cv2.FaceDetectorYN | None = None
        self._yunet_input: tuple[int, int] | None = None

        cascade_path = _resolve_cascade_path("haarcascade_frontalface_default.xml")
        self._cascade = cv2.CascadeClassifier(cascade_path)
        if self._cascade.empty():
            raise RuntimeError(
                f"Failed to load Haar cascade classifier (tried: {cascade_path})."
            )

        if self._backend in {"yunet", "auto"}:
            self._init_yunet()

    def _init_yunet(self) -> None:
        try:
            model_path = ensure_yunet_model()
            self._yunet = cv2.FaceDetectorYN.create(
                str(model_path),
                "",
                (320, 320),
                self._yunet_score,
                0.3,
                5000,
            )
            logger.info("YuNet face detector loaded")
        except Exception as exc:
            logger.warning("YuNet unavailable, using Haar only: %s", exc)
            self._yunet = None
            if self._backend == "yunet":
                raise

    def _enhance_bgr(self, frame: np.ndarray) -> list[np.ndarray]:
        variants = [frame]
        if not self._low_light:
            return variants

        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        l = clahe.apply(l)
        variants.append(cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR))

        bright = cv2.convertScaleAbs(frame, alpha=1.3, beta=25)
        variants.append(bright)
        return variants

    def _detect_yunet(self, frame: np.ndarray) -> list[tuple[int, int, int, int]]:
        if self._yunet is None:
            return []

        if frame.ndim != 3 or frame.shape[2] != 3:
            return []

        if frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)
        if not frame.flags["C_CONTIGUOUS"]:
            frame = np.ascontiguousarray(frame)

        height, width = frame.shape[:2]
        if width < 1 or height < 1:
            return []

        try:
            with AI_PIPELINE_LOCK:
                if self._yunet_input != (width, height):
                    self._yunet.setInputSize((width, height))
                    self._yunet_input = (width, height)

                _, faces = self._yunet.detect(frame)
        except cv2.error as exc:
            logger.warning("YuNet detect failed, falling back to Haar: %s", exc)
            return []

        if faces is None or len(faces) == 0:
            return []

        boxes: list[tuple[int, int, int, int]] = []
        for face in faces:
            x, y, w, h = face[0:4].astype(int)
            if w < self._min_size or h < self._min_size:
                continue
            boxes.append((max(0, x), max(0, y), w, h))
        return boxes

    def _detect_haar(self, frame: np.ndarray) -> list[tuple[int, int, int, int]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        all_boxes: list[tuple[int, int, int, int]] = []
        for variant in self._enhance_bgr(frame):
            g = cv2.cvtColor(variant, cv2.COLOR_BGR2GRAY) if variant.ndim == 3 else variant
            faces = self._cascade.detectMultiScale(
                g,
                scaleFactor=1.05,
                minNeighbors=3,
                minSize=(self._min_size, self._min_size),
                flags=cv2.CASCADE_SCALE_IMAGE,
            )
            all_boxes.extend((int(x), int(y), int(w), int(h)) for x, y, w, h in faces)

        return self._merge_boxes(all_boxes)

    def _merge_boxes(
        self,
        boxes: list[tuple[int, int, int, int]],
    ) -> list[tuple[int, int, int, int]]:
        if len(boxes) <= 1:
            return boxes

        merged: list[tuple[int, int, int, int]] = []
        used = [False] * len(boxes)

        for i, box_a in enumerate(boxes):
            if used[i]:
                continue
            ax, ay, aw, ah = box_a
            group = [box_a]
            used[i] = True
            acx, acy = ax + aw / 2, ay + ah / 2

            for j in range(i + 1, len(boxes)):
                if used[j]:
                    continue
                bx, by, bw, bh = boxes[j]
                bcx, bcy = bx + bw / 2, by + bh / 2
                if abs(acx - bcx) < max(aw, bw) * 0.5 and abs(acy - bcy) < max(ah, bh) * 0.5:
                    group.append(boxes[j])
                    used[j] = True

            xs = [b[0] for b in group]
            ys = [b[1] for b in group]
            x2 = [b[0] + b[2] for b in group]
            y2 = [b[1] + b[3] for b in group]
            merged.append((min(xs), min(ys), max(x2) - min(xs), max(y2) - min(ys)))

        return merged

    def detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int]]:
        if frame is None or frame.size == 0:
            return []

        try:
            return self._detect_impl(frame)
        except cv2.error as exc:
            logger.warning("Face detection failed: %s", exc)
            return []

    def _detect_impl(self, frame: np.ndarray) -> list[tuple[int, int, int, int]]:
        all_boxes: list[tuple[int, int, int, int]] = []

        if self._backend in {"yunet", "auto"} and self._yunet is not None:
            for variant in self._enhance_bgr(frame):
                all_boxes.extend(self._detect_yunet(variant))
            if all_boxes:
                return self._merge_boxes(all_boxes)[:5]

        if self._backend in {"haar", "auto"}:
            haar_boxes = self._detect_haar(frame)
            if haar_boxes:
                return haar_boxes[:5]

        return self._merge_boxes(all_boxes)[:5]

    def detect_stream(self, frame: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Fast Haar-only path for live video — no YuNet, no lock contention."""
        if frame is None or frame.size == 0:
            return []
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            faces = self._cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=3,
                minSize=(self._min_size, self._min_size),
                flags=cv2.CASCADE_SCALE_IMAGE,
            )
            return [(int(x), int(y), int(w), int(h)) for x, y, w, h in faces][:5]
        except cv2.error as exc:
            logger.warning("Stream face detection failed: %s", exc)
            return []
