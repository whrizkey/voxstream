from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import QSlider

    HAS_QT = True
else:
    try:
        from PySide6.QtCore import Qt, Signal
        from PySide6.QtWidgets import QSlider

        HAS_QT = True
    except ImportError:
        HAS_QT = False
        QSlider = object

        def Signal(*args: Any, **kwargs: Any) -> Any:
            return None


class ProcessedRegionSlider(QSlider if HAS_QT else object):  # type: ignore[misc]
    """Slider rendering both current playhead position and processed lookahead region."""

    if HAS_QT:
        seek_requested = Signal(float)

    def __init__(self, parent: Any = None) -> None:
        if not HAS_QT:
            return
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setRange(0, 1000)
        self.processed_ratio: float = 0.0
        self.duration: float = 1.0

    def set_processed_progress(self, processed_seconds: float, duration: float) -> None:
        """Update the secondary processed buffer indicator."""
        self.duration = max(0.1, duration)
        self.processed_ratio = max(0.0, min(1.0, processed_seconds / self.duration))
        if HAS_QT:
            self.update()

    def set_playhead(self, playhead_seconds: float, duration: float) -> None:
        """Update primary playhead position slider."""
        self.duration = max(0.1, duration)
        slider_val = int((playhead_seconds / self.duration) * 1000)
        if HAS_QT:
            self.setValue(slider_val)
