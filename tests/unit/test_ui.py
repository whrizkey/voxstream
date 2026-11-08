import os
from collections.abc import Generator
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from voxstream.ui.widgets.progress_bar import ProcessedRegionSlider
from voxstream.ui.widgets.status_pill import StatusPill


@pytest.fixture(autouse=True)
def ensure_qapp() -> Generator[Any, None, None]:
    """Ensure headless QApplication instance exists if Qt is available."""
    from voxstream.ui.widgets.status_pill import HAS_QT

    if not HAS_QT:
        yield None
        return

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    yield app


def test_status_pill_status_colors() -> None:
    pill = StatusPill()
    pill.set_status("Ready")
    assert pill.status == "Ready"
    pill.set_status("Buffering")
    assert pill.status == "Buffering"
    pill.set_status("Error")
    assert pill.status == "Error"


def test_processed_region_slider_ratios() -> None:
    slider = ProcessedRegionSlider()
    slider.set_processed_progress(30.0, 120.0)
    assert slider.processed_ratio == 0.25

    slider.set_processed_progress(150.0, 120.0)
    # Clamped to 1.0 max
    assert slider.processed_ratio == 1.0


def test_settings_dialog_masked_secrets() -> None:
    from voxstream.ui.settings_dialog import HAS_QT

    if not HAS_QT:
        return

    from voxstream.ui.settings_dialog import SettingsDialog

    dlg = SettingsDialog()
    # Ensure password echo mode is enabled for API key input fields
    from PySide6.QtWidgets import QLineEdit

    assert dlg.openai_key.echoMode() == QLineEdit.EchoMode.Password
    assert dlg.anthropic_key.echoMode() == QLineEdit.EchoMode.Password
