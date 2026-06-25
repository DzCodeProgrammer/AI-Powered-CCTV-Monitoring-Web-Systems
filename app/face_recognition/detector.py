from __future__ import annotations

import cv2
import numpy as np


class FaceDetector:
    def __init__(self) -> None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(cascade_path)
        if self._cascade.empty():
            raise RuntimeError("Failed to load Haar cascade classifier.")

    def detect(self, frame: np.ndarray) -> list[tuple[int, int, int, int]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._cascade.detectMultiScale(
            gray,
            scaleFactor=1.05,
            minNeighbors=4,
            minSize=(40, 40),
        )
        return [(int(x), int(y), int(w), int(h)) for x, y, w, h in faces]
