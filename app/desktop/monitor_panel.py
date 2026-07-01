"""Live CCTV panel with direct frame rendering (no browser / MJPEG)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.camera.stream_broadcaster import LiveStreamBroadcaster
from app.desktop.monitor_controller import (
    camera_last_error,
    monitoring_active,
    start_desktop_monitoring,
    stop_desktop_monitoring,
)
from app.desktop.qt_utils import bgr_to_qpixmap, fit_pixmap_to_label
from app.utils.config import get_settings


class MonitorPanel(QWidget):
    REFRESH_MS = 16

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        settings = get_settings()

        self._video = QLabel("Monitoring stopped")
        self._video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video.setMinimumHeight(360)
        self._video.setStyleSheet(
            "background-color: #111; color: #ccc; border-radius: 8px;"
        )

        self._status = QLabel("Status: Stopped")
        self._status.setStyleSheet("color: #444;")

        self._source = QComboBox()
        self._source.addItem("CCTV (Dahua/RTSP)", None)
        self._source.addItem("Webcam (built-in)", "0")
        self._source.addItem("Webcam #1 (USB)", "1")

        self._start_btn = QPushButton("Start monitoring")
        self._start_btn.clicked.connect(self._start)

        self._stop_btn = QPushButton("Stop monitoring")
        self._stop_btn.clicked.connect(self._stop)
        self._stop_btn.setEnabled(False)

        info = QLabel(
            f"Camera: {settings.safe_camera_display} · "
            f"Mode: {settings.cctv_mode} · Direct desktop stream"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-size: 12px;")

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Source:"))
        controls.addWidget(self._source)
        controls.addWidget(self._start_btn)
        controls.addWidget(self._stop_btn)
        controls.addStretch()
        controls.addWidget(self._status)

        layout = QVBoxLayout(self)
        layout.addWidget(self._video, stretch=1)
        layout.addLayout(controls)
        layout.addWidget(info)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_frame)
        self._display_max_width = settings.desktop_display_max_width

        if monitoring_active():
            self._sync_buttons(running=True)
            self._timer.start(self.REFRESH_MS)

    def current_source_override(self) -> str | None:
        return self._source.currentData()

    def sync_running_state(self) -> None:
        self._sync_buttons(True)
        self._timer.start(self.REFRESH_MS)

    def stop_from_tray(self) -> None:
        self._stop()

    def _sync_buttons(self, running: bool) -> None:
        self._start_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)
        self._source.setEnabled(not running)
        self._status.setText("Status: Live" if running else "Status: Stopped")

    def _start(self) -> None:
        source_override = self._source.currentData()
        self._video.setText("Connecting to camera...")
        try:
            start_desktop_monitoring(source_override)
        except Exception as exc:
            self._video.setText(f"Could not start camera:\n{exc}")
            return
        self._sync_buttons(True)
        self._timer.start(self.REFRESH_MS)
        if self.window() and hasattr(self.window(), "_tray"):
            self.window()._tray.refresh()  # type: ignore[attr-defined]

    def _stop(self) -> None:
        self._timer.stop()
        stop_desktop_monitoring()
        self._video.clear()
        self._video.setText("Monitoring stopped")
        self._sync_buttons(False)
        if self.window() and hasattr(self.window(), "_tray"):
            self.window()._tray.refresh()  # type: ignore[attr-defined]

    def _refresh_frame(self) -> None:
        try:
            self._refresh_frame_impl()
        except Exception as exc:
            self._status.setText(f"Status: display error — {exc}")

    def _refresh_frame_impl(self) -> None:
        broadcaster = LiveStreamBroadcaster.get()
        frame = broadcaster.get_latest_frame()
        if frame is not None:
            pixmap = bgr_to_qpixmap(frame, max_display_width=self._display_max_width)
            self._video.setPixmap(fit_pixmap_to_label(pixmap, self._video.size()))
            if broadcaster.is_connected:
                self._status.setText("Status: Live (connected)")
            else:
                error = camera_last_error()
                self._status.setText(
                    f"Status: no signal — {error}" if error else "Status: waiting for camera..."
                )
        elif not broadcaster.is_running:
            error = camera_last_error()
            if error:
                self._video.setText(f"Camera error:\n{error}")
                self._sync_buttons(False)
                self._timer.stop()
            else:
                self._video.setText("Monitoring stopped")

    def shutdown(self) -> None:
        self._timer.stop()
        if monitoring_active():
            stop_desktop_monitoring()
