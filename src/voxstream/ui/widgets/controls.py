from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QComboBox,
        QHBoxLayout,
        QPushButton,
        QSlider,
        QWidget,
    )

    HAS_QT = True
else:
    try:
        from PySide6.QtCore import Qt, Signal
        from PySide6.QtWidgets import (
            QComboBox,
            QHBoxLayout,
            QPushButton,
            QSlider,
            QWidget,
        )

        HAS_QT = True
    except ImportError:
        HAS_QT = False
        QWidget = object

        def Signal(*args: Any, **kwargs: Any) -> Any:
            return None


class TransportControls(QWidget if HAS_QT else object):  # type: ignore[misc]
    """Transport and mode control bar."""

    if HAS_QT:
        play_pause_clicked = Signal()
        mode_changed = Signal(str)
        language_changed = Signal(str)
        subtitles_toggled = Signal(bool)
        volume_changed = Signal(int)

    def __init__(self, parent: Any = None) -> None:
        if not HAS_QT:
            return
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Play / Pause button
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(lambda: self.play_pause_clicked.emit())
        layout.addWidget(self.play_btn)

        # Mode selector
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Subtitles Only", "Dubbing Only", "Both Subs & Dub", "Off"])
        self.mode_combo.currentTextChanged.connect(self._on_mode_change)
        layout.addWidget(self.mode_combo)

        # Target language dropdown
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(
            [
                "Spanish (es)",
                "Japanese (ja)",
                "German (de)",
                "French (fr)",
                "Chinese (zh)",
                "English (en)",
            ]
        )
        self.lang_combo.currentTextChanged.connect(self._on_lang_change)
        layout.addWidget(self.lang_combo)

        # Volume slider
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(100)
        self.vol_slider.valueChanged.connect(lambda v: self.volume_changed.emit(v))
        layout.addWidget(self.vol_slider)

    def _on_mode_change(self, text: str) -> None:
        mode_map = {
            "Subtitles Only": "subs",
            "Dubbing Only": "dub",
            "Both Subs & Dub": "both",
            "Off": "off",
        }
        if HAS_QT:
            self.mode_changed.emit(mode_map.get(text, "subs"))

    def _on_lang_change(self, text: str) -> None:
        # Extract code in parentheses
        code = text.split("(")[-1].rstrip(")")
        if HAS_QT:
            self.language_changed.emit(code)

    def set_playing(self, is_playing: bool) -> None:
        if HAS_QT:
            self.play_btn.setText("⏸ Pause" if is_playing else "▶ Play")
