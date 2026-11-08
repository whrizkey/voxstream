"""Video player abstractions supporting libmpv and virtual testing engines."""

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol


class Player(Protocol):
    """Protocol for video playback engines."""

    def load(self, media_path: Path | str) -> None: ...

    def play(self) -> None: ...

    def pause(self) -> None: ...

    def seek(self, target_seconds: float) -> None: ...

    def set_speed(self, speed: float) -> None: ...

    def set_volume(self, volume: float) -> None: ...

    def get_volume(self) -> float: ...

    def get_time_pos(self) -> float: ...

    def get_duration(self) -> float: ...

    def is_paused(self) -> bool: ...

    def register_time_pos_callback(self, callback: Callable[[float], None]) -> None: ...

    def register_seek_callback(self, callback: Callable[[float], None]) -> None: ...


class VirtualPlayer:
    """Deterministic, headless player clock for testing and CLI progress without GUI."""

    def __init__(self, duration: float = 120.0) -> None:
        self.duration = duration
        self._time_pos: float = 0.0
        self._paused: bool = True
        self._speed: float = 1.0
        self._volume: float = 100.0
        self._last_wall_time: float = time.monotonic()
        self._time_callbacks: list[Callable[[float], None]] = []
        self._seek_callbacks: list[Callable[[float], None]] = []

    def load(self, media_path: Path | str) -> None:
        self._time_pos = 0.0
        self._paused = True
        self._last_wall_time = time.monotonic()

    def play(self) -> None:
        if self._paused:
            self._paused = False
            self._last_wall_time = time.monotonic()

    def pause(self) -> None:
        self._update_pos()
        self._paused = True

    def seek(self, target_seconds: float) -> None:
        self._time_pos = max(0.0, min(self.duration, target_seconds))
        self._last_wall_time = time.monotonic()
        for cb in self._seek_callbacks:
            cb(self._time_pos)

    def set_speed(self, speed: float) -> None:
        self._update_pos()
        self._speed = max(0.1, min(4.0, speed))

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(100.0, volume))

    def get_volume(self) -> float:
        return self._volume

    def _update_pos(self) -> None:
        if not self._paused:
            now = time.monotonic()
            elapsed = (now - self._last_wall_time) * self._speed
            self._time_pos = min(self.duration, self._time_pos + elapsed)
            self._last_wall_time = now
            for cb in self._time_callbacks:
                cb(self._time_pos)

    def get_time_pos(self) -> float:
        self._update_pos()
        return self._time_pos

    def get_duration(self) -> float:
        return self.duration

    def is_paused(self) -> bool:
        return self._paused

    def register_time_pos_callback(self, callback: Callable[[float], None]) -> None:
        self._time_callbacks.append(callback)

    def register_seek_callback(self, callback: Callable[[float], None]) -> None:
        self._seek_callbacks.append(callback)

    def step_forward(self, seconds: float) -> None:
        """Advance simulated playback time deterministically."""
        self._time_pos = min(self.duration, self._time_pos + seconds)
        for cb in self._time_callbacks:
            cb(self._time_pos)


class MpvPlayer:
    """libmpv wrapper through python-mpv."""

    def __init__(self, **mpv_kwargs: Any) -> None:
        self._time_callbacks: list[Callable[[float], None]] = []
        self._seek_callbacks: list[Callable[[float], None]] = []
        self._volume: float = 100.0
        try:
            import mpv

            self._mpv = mpv.MPV(osc=True, ytdl=True, **mpv_kwargs)

            # Observe time-pos property for player time synchronization
            @self._mpv.property_observer("time-pos")  # type: ignore[untyped-decorator]
            def _on_time_pos(_name: str, value: Any) -> None:
                if value is not None:
                    pos = float(value)
                    for cb in self._time_callbacks:
                        cb(pos)

        except Exception:
            self._mpv = None

    def load(self, media_path: Path | str) -> None:
        if self._mpv:
            self._mpv.play(str(media_path))

    def play(self) -> None:
        if self._mpv:
            self._mpv.pause = False

    def pause(self) -> None:
        if self._mpv:
            self._mpv.pause = True

    def seek(self, target_seconds: float) -> None:
        if self._mpv:
            self._mpv.seek(target_seconds, reference="absolute")
            for cb in self._seek_callbacks:
                cb(target_seconds)

    def set_speed(self, speed: float) -> None:
        if self._mpv:
            self._mpv.speed = speed

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(100.0, volume))
        if self._mpv:
            self._mpv.volume = self._volume

    def get_volume(self) -> float:
        if self._mpv and self._mpv.volume is not None:
            return float(self._mpv.volume)
        return self._volume

    def get_time_pos(self) -> float:
        if self._mpv and self._mpv.time_pos is not None:
            return float(self._mpv.time_pos)
        return 0.0

    def get_duration(self) -> float:
        if self._mpv and self._mpv.duration is not None:
            return float(self._mpv.duration)
        return 0.0

    def is_paused(self) -> bool:
        if self._mpv and self._mpv.pause is not None:
            return bool(self._mpv.pause)
        return True

    def register_time_pos_callback(self, callback: Callable[[float], None]) -> None:
        self._time_callbacks.append(callback)

    def register_seek_callback(self, callback: Callable[[float], None]) -> None:
        self._seek_callbacks.append(callback)
