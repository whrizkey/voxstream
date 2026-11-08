from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel

    HAS_QT = True
else:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QLabel

        HAS_QT = True
    except ImportError:
        HAS_QT = False
        QLabel = object


class StatusPill(QLabel if HAS_QT else object):  # type: ignore[misc]
    """Colored status pill indicating player and scheduler status."""

    STATUS_COLORS: ClassVar[dict[str, str]] = {
        "Ready": "#10b981",  # Green
        "Processing": "#3b82f6",  # Blue
        "Buffering": "#f59e0b",  # Amber
        "Error": "#ef4444",  # Red
    }

    def __init__(self, parent: Any = None) -> None:
        if not HAS_QT:
            return
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_status("Ready")

    def set_status(self, status: str) -> None:
        self.status = status
        color = self.STATUS_COLORS.get(status, "#6b7280")
        if HAS_QT:
            self.setText(f"● {status}")
            self.setStyleSheet(
                f"background-color: rgba(255, 255, 255, 0.08); "
                f"color: {color}; "
                f"border: 1px solid {color}; "
                f"border-radius: 10px; "
                f"padding: 2px 10px; "
                f"font-weight: bold; "
                f"font-size: 11px;"
            )
