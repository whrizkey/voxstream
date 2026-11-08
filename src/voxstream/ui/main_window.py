from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QVBoxLayout,
        QWidget,
    )

    HAS_QT = True
else:
    try:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtWidgets import (
            QFileDialog,
            QHBoxLayout,
            QLabel,
            QMainWindow,
            QVBoxLayout,
            QWidget,
        )

        HAS_QT = True
    except ImportError:
        HAS_QT = False
        QMainWindow = object

from voxstream.playback.controller import PlaybackController
from voxstream.ui.settings_dialog import SettingsDialog
from voxstream.ui.widgets.controls import TransportControls
from voxstream.ui.widgets.progress_bar import ProcessedRegionSlider
from voxstream.ui.widgets.status_pill import StatusPill


class MainWindow(QMainWindow if HAS_QT else object):  # type: ignore[misc]
    """Main window with embedded video surface, subtitle overlay, and transport controls."""

    def __init__(self) -> None:
        if not HAS_QT:
            return
        super().__init__()
        self.setWindowTitle("VoxStream Player")
        self.resize(960, 600)
        self.setAcceptDrops(True)

        self.controller: PlaybackController | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        if not HAS_QT:
            return

        # Central Widget & Layout
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Top Bar: Status Pill & File info
        top_bar = QHBoxLayout()
        self.status_pill = StatusPill(self)
        top_bar.addWidget(self.status_pill)
        top_bar.addStretch()

        self.info_label = QLabel("Drag & drop a video file or choose File -> Open")
        top_bar.addWidget(self.info_label)
        main_layout.addLayout(top_bar)

        # Video Surface & Subtitle Overlay
        self.video_surface = QWidget(self)
        self.video_surface.setStyleSheet("background-color: #09090b; border-radius: 6px;")
        video_layout = QVBoxLayout(self.video_surface)
        video_layout.addStretch()

        # Subtitle overlay text label
        self.subtitle_label = QLabel("")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setStyleSheet(
            "color: #ffffff; "
            "font-size: 22px; "
            "font-weight: bold; "
            "background-color: rgba(0, 0, 0, 0.65); "
            "border-radius: 4px; "
            "padding: 6px 16px;"
        )
        self.subtitle_label.setVisible(False)
        video_layout.addWidget(self.subtitle_label)
        main_layout.addWidget(self.video_surface, stretch=1)

        # Seek Bar (with processed region lookahead)
        self.slider = ProcessedRegionSlider(self)
        main_layout.addWidget(self.slider)

        # Transport & Mode Controls
        self.controls = TransportControls(self)
        self.controls.play_pause_clicked.connect(self._toggle_play_pause)
        self.controls.mode_changed.connect(self._on_mode_change)
        self.controls.language_changed.connect(self._on_language_change)
        main_layout.addWidget(self.controls)

        # Menu Bar
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")

        open_action = file_menu.addAction("&Open File...")
        open_action.triggered.connect(self._open_file_dialog)

        settings_action = file_menu.addAction("&Settings...")
        settings_action.triggered.connect(self._open_settings)

        file_menu.addSeparator()
        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

        # Timer for subtitle and UI updates (100ms)
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(100)
        self.update_timer.timeout.connect(self._on_ui_tick)
        self.update_timer.start()

    def _open_file_dialog(self) -> None:
        if not HAS_QT:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Media File", "", "Videos (*.mp4 *.mkv *.webm *.mov *.wav *.mp3)"
        )
        if path:
            self.load_media(Path(path))

    def load_media(self, media_path: Path, target_lang: str = "es") -> None:
        self.controller = PlaybackController(media_path, target_lang=target_lang)
        self.info_label.setText(f"{media_path.name} ({self.controller.probe.duration:.1f}s)")
        self.status_pill.set_status("Processing")

    def _toggle_play_pause(self) -> None:
        if not self.controller:
            return
        if self.controller.player.is_paused():
            self.controller.play()
            self.controls.set_playing(True)
        else:
            self.controller.pause()
            self.controls.set_playing(False)

    def _on_mode_change(self, mode: str) -> None:
        if self.controller:
            self.controller.mode = mode

    def _on_language_change(self, lang_code: str) -> None:
        if self.controller:
            self.controller.target_lang = lang_code

    def _open_settings(self) -> None:
        if HAS_QT:
            dlg = SettingsDialog(self)
            dlg.exec()

    def _on_ui_tick(self) -> None:
        if not self.controller:
            return

        # 1. Update subtitle display
        cue = self.controller.get_active_subtitle()
        if cue and cue.text and self.controller.mode != "off":
            self.subtitle_label.setText(cue.text)
            self.subtitle_label.setVisible(True)
        else:
            self.subtitle_label.setVisible(False)

        # 2. Update status pill
        if self.controller.is_buffering:
            self.status_pill.set_status("Buffering")
        else:
            self.status_pill.set_status("Ready")

        # 3. Update seek bar
        pos = self.controller.player.get_time_pos()
        dur = self.controller.probe.duration
        self.slider.set_playhead(pos, dur)

    def keyPressEvent(self, event: Any) -> None:
        if not HAS_QT:
            return
        key = event.key()
        if key == Qt.Key.Key_Space:
            self._toggle_play_pause()
        elif key == Qt.Key.Key_Left and self.controller:
            self.controller.seek(max(0.0, self.controller.player.get_time_pos() - 5.0))
        elif key == Qt.Key.Key_Right and self.controller:
            self.controller.seek(self.controller.player.get_time_pos() + 5.0)
        elif key == Qt.Key.Key_F:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event: Any) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: Any) -> None:
        urls = event.mimeData().urls()
        if urls:
            path = Path(urls[0].toLocalFile())
            self.load_media(path)
