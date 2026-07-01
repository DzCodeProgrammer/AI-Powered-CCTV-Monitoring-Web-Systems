"""Recognition tuning and embedding rebuild for desktop."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.database.connection import SessionLocal
from app.services.model_settings_service import (
    apply_laptop_8gb_preset,
    save_model_settings,
    save_notification_settings,
)
from app.services.recognition_service import get_embedding_store, rebuild_embeddings
from app.utils.config import get_settings


class ModelSettingsPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        settings = get_settings()

        header = QLabel("Model & Performance Settings")
        header.setStyleSheet("font-size: 15px; font-weight: 600;")

        hint = QLabel(
            f"Face model: {settings.face_model} · "
            "Changes are saved to .env and applied immediately."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666; font-size: 12px;")

        self._threshold = QDoubleSpinBox()
        self._threshold.setRange(0.2, 0.8)
        self._threshold.setSingleStep(0.01)
        self._threshold.setDecimals(2)
        self._threshold.setValue(settings.recognition_threshold)

        self._margin = QDoubleSpinBox()
        self._margin.setRange(0.01, 0.25)
        self._margin.setSingleStep(0.01)
        self._margin.setDecimals(2)
        self._margin.setValue(settings.recognition_margin)

        self._interval = QDoubleSpinBox()
        self._interval.setRange(1.0, 300.0)
        self._interval.setSingleStep(1.0)
        self._interval.setDecimals(1)
        self._interval.setValue(settings.recognition_interval)

        self._frame_skip = QSpinBox()
        self._frame_skip.setRange(1, 6)
        self._frame_skip.setValue(settings.frame_skip)

        self._process_width = QSpinBox()
        self._process_width.setRange(320, 1280)
        self._process_width.setSingleStep(32)
        self._process_width.setValue(settings.process_max_width)

        self._max_faces = QSpinBox()
        self._max_faces.setRange(1, 4)
        self._max_faces.setValue(settings.max_faces_per_frame)

        self._registered = QLabel(self._registered_text())

        self._wa_enabled = QCheckBox("Enable WhatsApp notifications (Fonnte)")
        self._wa_enabled.setChecked(settings.wa_notify_enabled)

        self._wa_unknown = QCheckBox("Alert on unknown faces")
        self._wa_unknown.setChecked(settings.wa_notify_unknown)

        self._wa_attendance = QCheckBox("Send attendance to registered users")
        self._wa_attendance.setChecked(settings.wa_notify_attendance)

        form = QFormLayout()
        form.addRow("Recognition threshold", self._threshold)
        form.addRow("Recognition margin", self._margin)
        form.addRow("Recognition interval (s)", self._interval)
        form.addRow("Frame skip", self._frame_skip)
        form.addRow("Process max width (px)", self._process_width)
        form.addRow("Max faces per frame", self._max_faces)
        form.addRow("Registered persons", self._registered)

        wa_group = QGroupBox("WhatsApp notifications")
        wa_layout = QVBoxLayout(wa_group)
        wa_layout.addWidget(self._wa_enabled)
        wa_layout.addWidget(self._wa_unknown)
        wa_layout.addWidget(self._wa_attendance)
        wa_hint = QLabel("Token & phone numbers stay in .env (WA_API_TOKEN, WA_ADMIN_PHONES).")
        wa_hint.setStyleSheet("color: #666; font-size: 11px;")
        wa_hint.setWordWrap(True)
        wa_layout.addWidget(wa_hint)

        save_btn = QPushButton("Save settings")
        save_btn.clicked.connect(self._save)

        save_wa_btn = QPushButton("Save WhatsApp settings")
        save_wa_btn.clicked.connect(self._save_wa)

        preset_btn = QPushButton("Apply laptop 8GB preset")
        preset_btn.clicked.connect(self._apply_preset)

        rebuild_btn = QPushButton("Rebuild embeddings")
        rebuild_btn.clicked.connect(self._rebuild)

        actions = QHBoxLayout()
        actions.addWidget(save_btn)
        actions.addWidget(save_wa_btn)
        actions.addWidget(preset_btn)
        actions.addStretch()
        actions.addWidget(rebuild_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(hint)
        layout.addLayout(form)
        layout.addWidget(wa_group)
        layout.addLayout(actions)
        layout.addStretch()

    def _registered_text(self) -> str:
        store = get_embedding_store()
        count = len(store.entries) if store else 0
        return f"{count} embedding(s) loaded"

    def _save(self) -> None:
        try:
            save_model_settings(
                recognition_threshold=self._threshold.value(),
                recognition_margin=self._margin.value(),
                recognition_interval=self._interval.value(),
                frame_skip=self._frame_skip.value(),
                process_max_width=self._process_width.value(),
                max_faces_per_frame=self._max_faces.value(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Model settings", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Model settings", f"Save failed:\n{exc}")
            return

        self._registered.setText(self._registered_text())
        QMessageBox.information(self, "Model settings", "Settings saved and applied.")

    def _save_wa(self) -> None:
        settings = get_settings()
        try:
            save_notification_settings(
                wa_notify_enabled=self._wa_enabled.isChecked(),
                wa_api_token=settings.wa_api_token,
                wa_admin_phones=settings.wa_admin_phones,
                wa_notify_unknown=self._wa_unknown.isChecked(),
                wa_notify_attendance=self._wa_attendance.isChecked(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "WhatsApp settings", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "WhatsApp settings", f"Save failed:\n{exc}")
            return

        get_settings.cache_clear()
        refreshed = get_settings()
        self._wa_enabled.setChecked(refreshed.wa_notify_enabled)
        QMessageBox.information(
            self,
            "WhatsApp settings",
            "Saved. Notifications are "
            + ("enabled." if refreshed.wa_notify_enabled else "disabled."),
        )

    def _apply_preset(self) -> None:
        try:
            settings = apply_laptop_8gb_preset()
        except Exception as exc:
            QMessageBox.critical(self, "Model settings", f"Preset failed:\n{exc}")
            return

        self._threshold.setValue(settings.recognition_threshold)
        self._margin.setValue(settings.recognition_margin)
        self._interval.setValue(settings.recognition_interval)
        self._frame_skip.setValue(settings.frame_skip)
        self._process_width.setValue(settings.process_max_width)
        self._max_faces.setValue(settings.max_faces_per_frame)
        QMessageBox.information(
            self,
            "Model settings",
            "Laptop 8GB preset applied. Rebuild embeddings if you changed the face model.",
        )

    def _rebuild(self) -> None:
        reply = QMessageBox.question(
            self,
            "Rebuild embeddings",
            "Rebuild face embeddings from all registered users? This may take a minute.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        db = SessionLocal()
        try:
            store = rebuild_embeddings(db, get_settings())
            count = len(store.entries)
        except Exception as exc:
            QMessageBox.critical(self, "Rebuild embeddings", f"Failed:\n{exc}")
            return
        finally:
            db.close()

        self._registered.setText(self._registered_text())
        QMessageBox.information(
            self,
            "Rebuild embeddings",
            f"Embeddings rebuilt for {count} registered person(s).",
        )
