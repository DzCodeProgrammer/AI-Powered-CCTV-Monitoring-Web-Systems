from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field

import cv2
import numpy as np
from deepface import DeepFace

from app.face_recognition.detector import FaceDetector
from app.face_recognition.pipeline_lock import AI_PIPELINE_LOCK
from app.face_recognition.embeddings import (
    EmbeddingStore,
    cosine_distance,
    parse_embedding,
)
from app.face_recognition.frame_utils import crop_face, resize_frame, scale_bbox
from app.face_recognition.overlay import draw_face_boxes
from app.utils.config import Settings
from app.utils.logging import get_logger, log_exception

logger = get_logger("face_recognition")

STATUS_RECOGNIZED = "Recognized"
STATUS_UNKNOWN = "Unknown"
STATUS_DETECTING = "Detecting"


@dataclass
class FaceMatch:
    name: str
    status: str
    confidence: float
    user_id: int | None
    bbox: tuple[int, int, int, int]


@dataclass
class _FaceTrack:
    track_id: int
    bbox: tuple[int, int, int, int]
    name: str = "Detecting"
    status: str = STATUS_DETECTING
    confidence: float = 0.0
    user_id: int | None = None
    last_recognition: float = field(default_factory=lambda: 0.0)


@dataclass(frozen=True)
class RecognitionEvent:
    """A face that just finished async DeepFace recognition."""

    match: FaceMatch
    annotated_frame: np.ndarray


class FaceRecognizer:
    FACE_EMBED_MAX_SIZE = 160

    def __init__(self, settings: Settings, embedding_store: EmbeddingStore) -> None:
        self.settings = settings
        self.embedding_store = embedding_store
        self.detector = FaceDetector(settings)
        self._frame_index = 0
        self._tracks: list[_FaceTrack] = []
        self._last_matches: list[FaceMatch] = []
        self._perf = settings.performance_profile
        self._next_track_id = 1
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="deepface")
        self._in_flight: list[tuple[int, Future, np.ndarray]] = []
        self._pending_track_ids: set[int] = set()
        self._newly_recognized: list[RecognitionEvent] = []
        self._results_lock = threading.Lock()
        self._shutdown = False

    @property
    def is_shutdown(self) -> bool:
        return self._shutdown

    def shutdown(self, wait: bool = False) -> None:
        """Stop accepting DeepFace jobs — call before server exit."""
        self._shutdown = True
        self._executor.shutdown(wait=wait, cancel_futures=True)
        self._in_flight.clear()
        self._pending_track_ids.clear()

    def update_embeddings(self, embedding_store: EmbeddingStore) -> None:
        self.embedding_store = embedding_store

    def refresh_performance(self, settings: Settings | None = None) -> None:
        settings = settings or self.settings
        self.settings = settings
        self._perf = settings.performance_profile

    def reset_tracking(self) -> None:
        """Clear tracks when camera source changes."""
        self._frame_index = 0
        self._tracks = []
        self._last_matches = []
        self._pending_track_ids.clear()
        with self._results_lock:
            self._newly_recognized.clear()

    @property
    def deepface_call_count(self) -> int:
        return getattr(self, "_deepface_calls", 0)

    def warmup_model(self) -> None:
        """Pre-load TensorFlow / DeepFace weights to avoid a long first-frame delay."""
        try:
            rgb = np.zeros((96, 96, 3), dtype=np.uint8)
            DeepFace.represent(
                img_path=rgb,
                model_name=self.settings.face_model,
                enforce_detection=False,
                detector_backend="skip",
            )
            logger.info("DeepFace model warmup complete (%s)", self.settings.face_model)
        except Exception as exc:
            log_exception("face_recognition", "DeepFace warmup failed (non-fatal)", exc)

    def drain_recognition_events(self) -> list[RecognitionEvent]:
        with self._results_lock:
            events = self._newly_recognized[:]
            self._newly_recognized.clear()
        return events

    def flush_recognition(self, timeout: float = 5.0) -> None:
        """Wait for in-flight DeepFace jobs (used by tests)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._collect_recognition_results()
            if not self._in_flight:
                return
            time.sleep(0.02)
        self._collect_recognition_results()

    def _match_face(self, face_image: np.ndarray) -> tuple[str, str, float, int | None]:
        if self.embedding_store.is_empty() or face_image.size == 0:
            return "Unknown", STATUS_UNKNOWN, 0.0, None

        try:
            rgb = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
            height, width = rgb.shape[:2]
            if max(height, width) > self.FACE_EMBED_MAX_SIZE:
                scale = self.FACE_EMBED_MAX_SIZE / max(height, width)
                rgb = cv2.resize(
                    rgb,
                    (int(width * scale), int(height * scale)),
                    interpolation=cv2.INTER_AREA,
                )

            self._deepface_calls = getattr(self, "_deepface_calls", 0) + 1
            with AI_PIPELINE_LOCK:
                vector = DeepFace.represent(
                    img_path=rgb,
                    model_name=self.settings.face_model,
                    enforce_detection=False,
                    detector_backend="skip",
                )
            face_embedding = parse_embedding(vector)
        except Exception as exc:
            log_exception("face_recognition", "Face embedding failed during match", exc)
            return "Unknown", STATUS_UNKNOWN, 0.0, None

        distances = [
            cosine_distance(face_embedding, entry.embedding)
            for entry in self.embedding_store.entries
        ]
        ranked = sorted(enumerate(distances), key=lambda item: item[1])
        best_index, best_distance = ranked[0]
        best_distance = float(best_distance)
        best_entry = self.embedding_store.entries[best_index]

        if len(ranked) >= 2:
            second_best = float(ranked[1][1])
            margin = second_best - best_distance
            if margin < self.settings.recognition_margin:
                return "Unknown", STATUS_UNKNOWN, max(0.0, 1.0 - best_distance), None

        if best_distance < self.settings.recognition_threshold:
            confidence = max(0.0, 1.0 - best_distance)
            return best_entry.name, STATUS_RECOGNIZED, confidence, best_entry.user_id

        return "Unknown", STATUS_UNKNOWN, max(0.0, 1.0 - best_distance), None

    def _find_track(self, track_id: int) -> _FaceTrack | None:
        for track in self._tracks:
            if track.track_id == track_id:
                return track
        return None

    def _bbox_center(self, bbox: tuple[int, int, int, int]) -> tuple[float, float]:
        x, y, w, h = bbox
        return x + w / 2, y + h / 2

    def _bbox_distance(
        self,
        a: tuple[int, int, int, int],
        b: tuple[int, int, int, int],
    ) -> float:
        ax, ay = self._bbox_center(a)
        bx, by = self._bbox_center(b)
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

    def _update_tracks(self, bboxes: list[tuple[int, int, int, int]]) -> None:
        max_faces = int(self._perf["max_faces_per_frame"])
        bboxes = bboxes[:max_faces]
        used: set[int] = set()
        new_tracks: list[_FaceTrack] = []

        for bbox in bboxes:
            best_idx = None
            best_dist = float("inf")
            for idx, track in enumerate(self._tracks):
                if idx in used:
                    continue
                dist = self._bbox_distance(bbox, track.bbox)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = idx

            if best_idx is not None and best_dist < 80:
                used.add(best_idx)
                old = self._tracks[best_idx]
                new_tracks.append(
                    _FaceTrack(
                        track_id=old.track_id,
                        bbox=bbox,
                        name=old.name,
                        status=old.status,
                        confidence=old.confidence,
                        user_id=old.user_id,
                        last_recognition=old.last_recognition,
                    )
                )
            else:
                new_tracks.append(_FaceTrack(track_id=self._next_track_id, bbox=bbox))
                self._next_track_id += 1

        self._tracks = new_tracks

    def _should_schedule_recognition(self, track: _FaceTrack, now: float) -> bool:
        if track.track_id in self._pending_track_ids:
            return False
        interval = float(self._perf["recognition_interval"])
        if track.last_recognition <= 0:
            return True
        return (now - track.last_recognition) >= interval

    def _schedule_recognition(
        self,
        track: _FaceTrack,
        display_frame: np.ndarray,
        full_frame: np.ndarray,
    ) -> None:
        now = time.time()
        if not self._should_schedule_recognition(track, now):
            return

        roi = crop_face(full_frame, track.bbox)
        if roi.size == 0:
            return

        track.last_recognition = now
        self._pending_track_ids.add(track.track_id)
        snapshot = display_frame.copy()
        track_id = track.track_id

        if self._shutdown:
            return
        try:
            future = self._executor.submit(self._match_face, roi.copy())
        except RuntimeError:
            return
        self._in_flight.append((track_id, future, snapshot))

    def _collect_recognition_results(self) -> None:
        still_pending: list[tuple[int, Future, np.ndarray]] = []
        for track_id, future, snapshot in self._in_flight:
            if not future.done():
                still_pending.append((track_id, future, snapshot))
                continue

            self._pending_track_ids.discard(track_id)
            try:
                name, status, confidence, user_id = future.result()
            except Exception as exc:
                log_exception("face_recognition", "Async recognition failed", exc)
                continue

            track = self._find_track(track_id)
            if track is None:
                continue

            track.name = name
            track.status = status
            track.confidence = confidence
            track.user_id = user_id

            match = FaceMatch(
                name=track.name,
                status=track.status,
                confidence=track.confidence,
                user_id=track.user_id,
                bbox=track.bbox,
            )
            annotated = snapshot.copy()
            draw_face_boxes(annotated, [match])
            with self._results_lock:
                self._newly_recognized.append(RecognitionEvent(match=match, annotated_frame=annotated))

        self._in_flight = still_pending

    def _tracks_to_matches(self) -> list[FaceMatch]:
        return [
            FaceMatch(
                name=track.name,
                status=track.status,
                confidence=track.confidence,
                user_id=track.user_id,
                bbox=track.bbox,
            )
            for track in self._tracks
        ]

    def process_snapshot(self, frame: np.ndarray) -> tuple[np.ndarray, list[FaceMatch]]:
        """One-shot detect + recognize for event snapshots (blocking)."""
        perf = self._perf
        proc_frame, proc_scale = resize_frame(frame, int(perf["process_max_width"]))
        bboxes = self.detector.detect(proc_frame)
        max_faces = int(perf["max_faces_per_frame"])
        matches: list[FaceMatch] = []

        for bbox in bboxes[:max_faces]:
            full_bbox = scale_bbox(bbox, proc_scale)
            face_roi = crop_face(frame, full_bbox)
            name, status, confidence, user_id = self._match_face(face_roi)
            matches.append(
                FaceMatch(
                    name=name,
                    status=status,
                    confidence=confidence,
                    user_id=user_id,
                    bbox=full_bbox,
                )
            )

        annotated = frame.copy()
        draw_face_boxes(annotated, matches)
        return annotated, matches

    def preview_stream_frame(self, frame: np.ndarray) -> np.ndarray:
        """Resize + last overlays only — keeps live video smooth while AI catches up."""
        self._collect_recognition_results()
        display, _ = resize_frame(frame, int(self._perf["stream_max_width"]))
        return draw_face_boxes(display, self._tracks_to_matches())

    def annotate_stream_frame(
        self,
        frame: np.ndarray,
        *,
        run_ai: bool = True,
    ) -> tuple[np.ndarray, list[FaceMatch]]:
        """Fast stream path: always show the latest camera frame with overlays."""
        if self._shutdown:
            display, _ = resize_frame(frame, int(self._perf["stream_max_width"]))
            return draw_face_boxes(display, self._last_matches), self._last_matches

        self._collect_recognition_results()

        perf = self._perf
        display, display_scale = resize_frame(frame, int(perf["stream_max_width"]))

        if run_ai:
            self._frame_index += 1
            frame_skip = max(1, int(perf["frame_skip"]))
            detect_every = max(1, frame_skip * int(perf["detection_frame_skip"]))
            if not self._tracks or self._frame_index % detect_every == 0:
                proc_frame, proc_scale = resize_frame(frame, int(perf["process_max_width"]))
                bboxes = self.detector.detect_stream(proc_frame)
                full_bboxes = [scale_bbox(b, proc_scale) for b in bboxes]
                display_bboxes = [scale_bbox(b, 1 / display_scale) for b in full_bboxes]
                self._update_tracks(display_bboxes)

            for track in self._tracks:
                self._schedule_recognition(track, display, frame)

        matches = self._tracks_to_matches()
        self._last_matches = matches
        annotated = draw_face_boxes(display, matches)

        return annotated, matches

    def process_frame(self, frame: np.ndarray) -> tuple[np.ndarray, list[FaceMatch]]:
        """Legacy/test entry: honour frame_skip before running AI."""
        frame_skip = max(1, int(self._perf["frame_skip"]))
        run_ai = (self._frame_index % frame_skip) == 0
        self._frame_index += 1
        return self.annotate_stream_frame(frame, run_ai=run_ai)
