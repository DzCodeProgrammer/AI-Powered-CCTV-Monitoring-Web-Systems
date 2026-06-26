"""Central logging — all errors written to the logs/ folder."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_configured = False


def setup_logging(log_dir: str | Path | None = None) -> None:
    global _configured
    if _configured:
        return

    from app.utils.config import get_settings

    settings = get_settings()
    log_path = Path(log_dir or settings.log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(formatter)
        root.addHandler(console)

    if not any(
        isinstance(h, RotatingFileHandler) and "app.log" in getattr(h, "baseFilename", "")
        for h in root.handlers
    ):
        app_handler = RotatingFileHandler(
            log_path / "app.log",
            maxBytes=5_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        app_handler.setLevel(logging.INFO)
        app_handler.setFormatter(formatter)
        root.addHandler(app_handler)

    if not any(
        isinstance(h, RotatingFileHandler) and "errors.log" in getattr(h, "baseFilename", "")
        for h in root.handlers
    ):
        error_handler = RotatingFileHandler(
            log_path / "errors.log",
            maxBytes=5_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root.addHandler(error_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


def log_exception(category: str, message: str, exc: BaseException | None = None) -> None:
    logger = get_logger(category)
    if exc is not None:
        logger.error("%s: %s", message, exc, exc_info=exc)
    else:
        logger.error(message)
