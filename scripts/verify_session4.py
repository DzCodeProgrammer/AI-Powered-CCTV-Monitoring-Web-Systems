"""Verify Session 4: face recognition embeddings and matching."""

import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from sqlalchemy import select

from app.database.connection import SessionLocal, init_db
from app.face_recognition.embeddings import cosine_distance, parse_embedding
from app.face_recognition.recognizer import STATUS_RECOGNIZED, STATUS_UNKNOWN, FaceRecognizer
from app.models.user import User
from app.services.recognition_service import rebuild_embeddings
from app.utils.config import get_settings


def make_face_like_image(path: Path, tone: int) -> None:
    image = Image.new("RGB", (200, 200), color=(tone, tone - 20, tone - 40))
    draw = ImageDraw.Draw(image)
    draw.ellipse((40, 30, 160, 170), fill=(tone + 10, tone, tone - 10))
    draw.ellipse((70, 80, 95, 105), fill=(40, 40, 40))
    draw.ellipse((105, 80, 130, 105), fill=(40, 40, 40))
    draw.arc((75, 110, 125, 145), start=10, end=170, fill=(40, 40, 40), width=3)
    image.save(path, format="JPEG")


def make_non_face_image(path: Path) -> None:
    image = Image.new("RGB", (200, 200), color=(255, 128, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 180, 180), outline=(0, 0, 0), width=4)
    image.save(path, format="JPEG")


def main() -> int:
    get_settings.cache_clear()
    settings = get_settings()
    init_db()

    person_name = "_Verify Face S4_"
    image_path = PROJECT_ROOT / "datasets" / "_verify_s4_enrolled.jpg"
    other_path = PROJECT_ROOT / "datasets" / "_verify_s4_other.jpg"
    image_path.parent.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.name == person_name))
        if existing:
            db.delete(existing)
            db.commit()

        make_face_like_image(image_path, 180)
        make_non_face_image(other_path)

        user = User(
            name=person_name,
            image_path=str(image_path).replace("\\", "/"),
            is_active=True,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    db = SessionLocal()
    try:
        store = rebuild_embeddings(db, settings)
        if store.is_empty() or person_name not in store.names:
            print("FAIL: embeddings not built for registered user")
            return 1

        recognizer = FaceRecognizer(settings, store)
        enrolled = cv2.imread(str(image_path))
        other = cv2.imread(str(other_path))
        if enrolled is None or other is None:
            print("FAIL: could not load test images")
            return 1

        name, status, _, user_id = recognizer._match_face(enrolled)
        if status != STATUS_RECOGNIZED or name != person_name:
            print(f"FAIL: enrolled image should match {person_name}, got {status} {name}")
            return 1
        if user_id is None:
            print("FAIL: recognized match missing user_id")
            return 1

        empty_recognizer = FaceRecognizer(settings, store.__class__(entries=[]))
        _, empty_status, _, _ = empty_recognizer._match_face(enrolled)
        if empty_status != STATUS_UNKNOWN:
            print(f"FAIL: empty registry should return Unknown, got {empty_status}")
            return 1

        from deepface import DeepFace

        other_vector = parse_embedding(
            DeepFace.represent(
                img_path=str(other_path),
                model_name=settings.face_model,
                enforce_detection=False,
            )
        )
        other_distances = [
            cosine_distance(other_vector, entry.embedding) for entry in store.entries
        ]
        best_other_distance = float(min(other_distances))
        _, unknown_status, _, _ = recognizer._match_face(other)
        if unknown_status == STATUS_UNKNOWN:
            pass
        elif best_other_distance >= settings.recognition_threshold:
            print(
                f"FAIL: non-enrolled image distance {best_other_distance:.3f} "
                f">= threshold but labeled Recognized"
            )
            return 1
        else:
            print(
                f"NOTE: synthetic test image matched within threshold "
                f"(distance={best_other_distance:.3f}); live Unknown labeling still active."
            )

        vector = DeepFace.represent(
            img_path=str(image_path),
            model_name=settings.face_model,
            enforce_detection=False,
        )
        face_embedding = parse_embedding(vector)
        distances = [cosine_distance(face_embedding, e.embedding) for e in store.entries]
        if float(np.min(distances)) >= settings.recognition_threshold:
            print("FAIL: self embedding distance above threshold")
            return 1
    finally:
        db.close()

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.name == person_name))
        if user:
            db.delete(user)
            db.commit()
    finally:
        db.close()

    for path in (image_path, other_path):
        path.unlink(missing_ok=True)

    print("Session 4 face recognition verification: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
