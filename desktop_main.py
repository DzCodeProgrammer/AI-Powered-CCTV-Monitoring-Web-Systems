"""Smart CCTV — native desktop entry point (single admin laptop)."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from PySide6.QtCore import QSharedMemory
from PySide6.QtWidgets import QApplication, QMessageBox


def _apply_desktop_env_defaults() -> None:
    """Desktop-only defaults when keys are absent from .env (Phase 3)."""
    os.environ["DESKTOP_MODE"] = "true"
    os.environ.setdefault(
        "OPENCV_FFMPEG_CAPTURE_OPTIONS",
        "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;0",
    )

    env_path = Path(".env")
    env_text = env_path.read_text(encoding="utf-8") if env_path.is_file() else ""

    def missing(key: str) -> bool:
        return not re.search(rf"^\s*{re.escape(key)}\s*=", env_text, flags=re.I | re.M)

    if missing("CCTV_MODE"):
        os.environ.setdefault("CCTV_MODE", "event")
    if missing("HOST"):
        os.environ.setdefault("HOST", "127.0.0.1")
    if missing("DESKTOP_DISPLAY_MAX_WIDTH"):
        os.environ.setdefault("DESKTOP_DISPLAY_MAX_WIDTH", "640")
    if missing("RECOGNITION_INTERVAL"):
        os.environ.setdefault("RECOGNITION_INTERVAL", "1")
    if missing("FRAME_SKIP"):
        os.environ.setdefault("FRAME_SKIP", "1")


def _ensure_single_instance(app: QApplication) -> bool:
    shared = QSharedMemory("SmartCCTVDesktop")
    if shared.attach():
        QMessageBox.warning(
            None,
            "Smart CCTV",
            "Application is already running on this laptop.",
        )
        return False
    if not shared.create(1):
        return True
    app.shared_memory = shared  # type: ignore[attr-defined]
    return True


def _install_crash_handlers(app: QApplication) -> None:
    """Log uncaught errors instead of silently killing the desktop process."""
    import traceback

    from PySide6.QtCore import QtMsgType, qInstallMessageHandler

    from app.utils.logging import get_logger

    log = get_logger("desktop")

    def _excepthook(exc_type, exc, tb) -> None:
        log.error("Uncaught exception:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))
        QMessageBox.critical(
            None,
            "Smart CCTV — Error",
            f"An error occurred but the app will keep running.\n\n{exc}",
        )

    sys.excepthook = _excepthook

    def _qt_handler(msg_type, context, message) -> None:  # noqa: ARG001
        if msg_type in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            log.error("Qt %s: %s", msg_type, message)

    try:
        qInstallMessageHandler(_qt_handler)
    except Exception:
        pass

    app.setQuitOnLastWindowClosed(True)


def main() -> int:
    _apply_desktop_env_defaults()

    from app.desktop.async_runtime import start_background_tasks
    from app.desktop.bootstrap import init_desktop_core
    from app.desktop.login_dialog import LoginDialog
    from app.desktop.main_window import MainWindow

    init_desktop_core()

    app = QApplication(sys.argv)
    app.setApplicationName("Smart CCTV Desktop")
    app.setOrganizationName("SmartCCTV")
    _install_crash_handlers(app)

    if not _ensure_single_instance(app):
        return 1

    start_background_tasks()

    login = LoginDialog()
    if login.exec() != LoginDialog.DialogCode.Accepted or login.admin is None:
        from app.desktop.async_runtime import stop_background_tasks

        stop_background_tasks()
        return 0

    window = MainWindow(login.admin)
    window.show()
    code = app.exec()

    from app.desktop.async_runtime import stop_background_tasks
    from app.services.monitoring_service import shutdown_monitoring

    shutdown_monitoring()
    stop_background_tasks()
    return code


if __name__ == "__main__":
    sys.exit(main())
