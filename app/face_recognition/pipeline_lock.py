"""Serialize OpenCV DNN / DeepFace calls — not thread-safe across stream + event threads."""

from __future__ import annotations

import threading

AI_PIPELINE_LOCK = threading.RLock()
