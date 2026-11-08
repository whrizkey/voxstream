from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QDoubleSpinBox,
        QFormLayout,
        QLineEdit,
        QVBoxLayout,
    )

    HAS_QT = True
else:
    try:
        from PySide6.QtWidgets import (
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QFormLayout,
            QLineEdit,
            QVBoxLayout,
        )

        HAS_QT = True
    except ImportError:
        HAS_QT = False
        QDialog = object

from voxstream.config import get_settings


class SettingsDialog(QDialog if HAS_QT else object):  # type: ignore[misc]
    """Modal dialog for configuring providers, parameters, and masked API credentials."""

    def __init__(self, parent: Any = None) -> None:
        if not HAS_QT:
            return
        super().__init__(parent)
        self.setWindowTitle("VoxStream Settings")
        self.setMinimumWidth(450)

        self.settings = get_settings()
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Providers
        self.stt_combo = QComboBox()
        self.stt_combo.addItems(["faster_whisper", "openai_compat", "fake"])
        self.stt_combo.setCurrentText(self.settings.stt_provider)
        form.addRow("STT Provider:", self.stt_combo)

        self.trans_combo = QComboBox()
        self.trans_combo.addItems(["openai_compat", "anthropic", "deepl", "fake"])
        self.trans_combo.setCurrentText(self.settings.translate_provider)
        form.addRow("Translate Provider:", self.trans_combo)

        self.tts_combo = QComboBox()
        self.tts_combo.addItems(["edge", "openai", "elevenlabs", "piper", "fake"])
        self.tts_combo.setCurrentText(self.settings.tts_provider)
        form.addRow("TTS Provider:", self.tts_combo)

        # Masked API Keys (password echo mode)
        self.openai_key = QLineEdit()
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        if self.settings.openai_api_key:
            self.openai_key.setText(self.settings.openai_api_key)
        form.addRow("OpenAI API Key:", self.openai_key)

        self.anthropic_key = QLineEdit()
        self.anthropic_key.setEchoMode(QLineEdit.EchoMode.Password)
        if self.settings.anthropic_api_key:
            self.anthropic_key.setText(self.settings.anthropic_api_key)
        form.addRow("Anthropic API Key:", self.anthropic_key)

        # Lookahead & Audio Tuning
        self.lookahead_spin = QDoubleSpinBox()
        self.lookahead_spin.setRange(10.0, 300.0)
        self.lookahead_spin.setValue(self.settings.lookahead_seconds)
        form.addRow("Lookahead (seconds):", self.lookahead_spin)

        self.duck_spin = QDoubleSpinBox()
        self.duck_spin.setRange(-40.0, 0.0)
        self.duck_spin.setValue(self.settings.duck_db)
        form.addRow("Ducking Level (dB):", self.duck_spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
