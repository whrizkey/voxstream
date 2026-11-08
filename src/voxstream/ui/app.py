"""Desktop application launcher."""

import sys
from pathlib import Path

from voxstream.errors import ConfigurationError


def run_desktop_app(initial_file: str | None = None) -> int:
    """Launch the VoxStream PySide6 desktop GUI."""
    try:
        from PySide6.QtWidgets import QApplication

        from voxstream.ui.main_window import MainWindow
    except ImportError as exc:
        raise ConfigurationError(
            "PySide6 is not installed. Install with `pip install PySide6` or `uv sync --extra gui`."
        ) from exc

    app = QApplication(sys.argv)
    window = MainWindow()

    if initial_file:
        file_path = Path(initial_file)
        if file_path.exists():
            window.load_media(file_path)

    window.show()
    return int(app.exec())
