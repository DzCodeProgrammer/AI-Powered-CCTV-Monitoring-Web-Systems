from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from deepface import DeepFace
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.utils.config import Settings


@dataclass
class EmbeddingEntry:
    user_id: int
    name: str
    embedding: np.ndarray


@dataclass
class EmbeddingStore:
    entries: list[EmbeddingEntry]

    @property
    def names(self) -> list[str]:
        return [entry.name for entry in self.entries]

    @property
    def vectors(self) -> np.ndarray:
        if not self.entries:
            return np.empty((0, 0))
        return np.vstack([entry.embedding for entry in self.entries])

    def is_empty(self) -> bool:
        return len(self.entries) == 0


def parse_embedding(vec) -> np.ndarray:
    if isinstance(vec, list) and len(vec) > 0:
        first = vec[0]
        if isinstance(first, dict) and "embedding" in first:
            return np.array(first["embedding"], dtype=float)
        return np.array(first, dtype=float)
    if isinstance(vec, dict) and "embedding" in vec:
        return np.array(vec["embedding"], dtype=float)
    return np.array(vec, dtype=float)


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(float)
    b = b.astype(float)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - (np.dot(a, b) / (norm_a * norm_b))


def embeddings_cache_path(settings: Settings) -> Path:
    return Path("database") / "embeddings.pkl"


def build_embeddings_from_db(db: Session, settings: Settings) -> EmbeddingStore:
    users = db.scalars(
        select(User).where(User.is_active.is_(True)).order_by(User.id)
    ).all()

    entries: list[EmbeddingEntry] = []
    for user in users:
        image_path = Path(user.image_path)
        if not image_path.is_file():
            continue
        try:
            vector = DeepFace.represent(
                img_path=str(image_path),
                model_name=settings.face_model,
                enforce_detection=False,
            )
            embedding = parse_embedding(vector)
            if embedding.size == 0:
                continue
            entries.append(
                EmbeddingEntry(user_id=user.id, name=user.name, embedding=embedding)
            )
            user.embedding_path = str(embeddings_cache_path(settings))
        except Exception:
            continue

    db.commit()
    return EmbeddingStore(entries=entries)


def save_embedding_store(store: EmbeddingStore, settings: Settings) -> Path:
    cache_path = embeddings_cache_path(settings)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "entries": [
            {
                "user_id": entry.user_id,
                "name": entry.name,
                "embedding": entry.embedding,
            }
            for entry in store.entries
        ]
    }
    with cache_path.open("wb") as handle:
        pickle.dump(payload, handle)
    return cache_path


def load_embedding_store(settings: Settings) -> EmbeddingStore | None:
    cache_path = embeddings_cache_path(settings)
    if not cache_path.is_file():
        return None
    with cache_path.open("rb") as handle:
        payload = pickle.load(handle)
    entries = [
        EmbeddingEntry(
            user_id=item["user_id"],
            name=item["name"],
            embedding=np.array(item["embedding"], dtype=float),
        )
        for item in payload.get("entries", [])
    ]
    return EmbeddingStore(entries=entries)


def ensure_embeddings(db: Session, settings: Settings, force: bool = False) -> EmbeddingStore:
    if not force:
        cached = load_embedding_store(settings)
        if cached is not None and not cached.is_empty():
            return cached
    store = build_embeddings_from_db(db, settings)
    save_embedding_store(store, settings)
    return store
