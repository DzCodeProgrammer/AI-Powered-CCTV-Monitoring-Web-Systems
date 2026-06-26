from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from app.utils.logging import log_exception

from app.face_recognition.detector import FaceDetector
from app.face_recognition.embeddings import (
    EmbeddingStore,
    cosine_distance,
    parse_embedding,
)
from app.utils.config import Settings

STATUS_RECOGNIZED = "Recognized"
STATUS_UNKNOWN = "Unknown"


@dataclass
class FaceMatch:
    name: str
    status: str
    confidence: float
    user_id: int | None
    bbox: tuple[int, int, int, int]


class FaceRecognizer:
    def __init__(self, settings: Settings, embedding_store: EmbeddingStore) -> None:
        self.settings = settings
        self.embedding_store = embedding_store
        self.detector = FaceDetector()

    def update_embeddings(self, embedding_store: EmbeddingStore) -> None:
        self.embedding_store = embedding_store

    def _match_face(self, face_image: np.ndarray) -> tuple[str, str, float, int | None]:
        if self.embedding_store.is_empty():
            return "Unknown", STATUS_UNKNOWN, 0.0, None

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp_path = tmp.name
                cv2.imwrite(tmp_path, face_image)

            vector = DeepFace.represent(
                img_path=tmp_path,
                model_name=self.settings.face_model,
                enforce_detection=False,
            )
            face_embedding = parse_embedding(vector)
        except Exception as exc:
            log_exception("face_recognition", "Face embedding failed during match", exc)
            return "Unknown", STATUS_UNKNOWN, 0.0, None
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

        distances = [
            cosine_distance(face_embedding, entry.embedding)
            for entry in self.embedding_store.entries
        ]
        best_index = int(np.argmin(distances))
        best_distance = float(distances[best_index])
        best_entry = self.embedding_store.entries[best_index]

        if best_distance < self.settings.recognition_threshold:
            confidence = max(0.0, 1.0 - best_distance)
            return best_entry.name, STATUS_RECOGNIZED, confidence, best_entry.user_id

        return "Unknown", STATUS_UNKNOWN, max(0.0, 1.0 - best_distance), None

    def process_frame(self, frame: np.ndarray) -> tuple[np.ndarray, list[FaceMatch]]:
        matches: list[FaceMatch] = []
        annotated = frame.copy()

        for x, y, w, h in self.detector.detect(frame):
            face_roi = frame[y : y + h, x : x + w]
            name, status, confidence, user_id = self._match_face(face_roi)
            match = FaceMatch(
                name=name,
                status=status,
                confidence=confidence,
                user_id=user_id,
                bbox=(x, y, w, h),
            )
            matches.append(match)

            color = (0, 200, 0) if status == STATUS_RECOGNIZED else (0, 0, 220)
            label = name if status == STATUS_RECOGNIZED else "Unknown"
            confidence_pct = int(round(confidence * 100))
            display_label = f"{label} {confidence_pct}%"
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
            cv2.putText(
                annotated,
                display_label,
                (x, max(y - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                color,
                2,
            )

        if not matches:
            cv2.putText(
                annotated,
                "No face detected",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2,
            )

        return annotated, matches
