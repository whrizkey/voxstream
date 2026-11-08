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


def _load_keyring_secret(service: str, username: str, fallback: str | None) -> str:
    """Read a stored secret from the system keyring if available."""
    try:
        import keyring

        val = keyring.get_password(service, username)
        if val:
            return str(val)
    except Exception:
        pass
    return fallback or ""


def _save_keyring_secret(service: str, username: str, value: str) -> None:
    """Store or remove a secret in the system keyring."""
    try:
        import keyring

        if value:
            keyring.set_password(service, username, value)
        else:
            try:
                keyring.delete_password(service, username)
            except Exception:
                pass
    except Exception:
        pass


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

        # Masked API Keys (password echo mode with keyring integration)
        self.openai_key = QLineEdit()
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key.setText(
            _load_keyring_secret("voxstream", "openai_api_key", self.settings.openai_key_str)
        )
        form.addRow("OpenAI API Key:", self.openai_key)

        self.anthropic_key = QLineEdit()
        self.anthropic_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_key.setText(
            _load_keyring_secret("voxstream", "anthropic_api_key", self.settings.anthropic_key_str)
        )
        form.addRow("Anthropic API Key:", self.anthropic_key)

        self.deepl_key = QLineEdit()
        self.deepl_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.deepl_key.setText(
            _load_keyring_secret("voxstream", "deepl_api_key", self.settings.deepl_key_str)
        )
        form.addRow("DeepL API Key:", self.deepl_key)

        self.elevenlabs_key = QLineEdit()
        self.elevenlabs_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.elevenlabs_key.setText(
            _load_keyring_secret(
                "voxstream", "elevenlabs_api_key", self.settings.elevenlabs_key_str
            )
        )
        form.addRow("ElevenLabs API Key:", self.elevenlabs_key)

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

    def accept(self) -> None:
        if HAS_QT:
            _save_keyring_secret("voxstream", "openai_api_key", self.openai_key.text().strip())
            _save_keyring_secret(
                "voxstream", "anthropic_api_key", self.anthropic_key.text().strip()
            )
            _save_keyring_secret("voxstream", "deepl_api_key", self.deepl_key.text().strip())
            _save_keyring_secret(
                "voxstream", "elevenlabs_api_key", self.elevenlabs_key.text().strip()
            )
            super().accept()
