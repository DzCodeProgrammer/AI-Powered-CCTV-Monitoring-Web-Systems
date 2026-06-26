from __future__ import annotations

import cv2
import numpy as np


def make_status_frame(
    message: str,
    submessage: str = "",
    width: int = 1280,
    height: int = 720,
) -> np.ndarray:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = (32, 32, 32)

    cv2.putText(
        frame,
        message,
        (40, height // 2 - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 255),
        2,
    )
    if submessage:
        cv2.putText(
            frame,
            submessage,
            (40, height // 2 + 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (200, 200, 200),
            2,
        )
    return frame
