"""Real-time PortAudio dub mixer with master clock slaved to mpv time-pos."""

import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import soundfile as sf

from voxstream.models import DubClip


@dataclass
class ClockAnchor:
    media_time: float
    mono_time: float
    speed: float = 1.0


class DubMixer:
    """Audio output mixer slaved to video player clock with drift compensation."""

    def __init__(
        self,
        sample_rate: int = 24000,
        duck_db: float = -14.0,
        drift_threshold: float = 0.08,
        latency_offset_ms: float = 0.0,
    ) -> None:
        self.sample_rate = sample_rate
        self.duck_db = duck_db
        self.drift_threshold = drift_threshold
        self.latency_offset_seconds = latency_offset_ms / 1000.0

        self.anchor = ClockAnchor(media_time=0.0, mono_time=time.monotonic(), speed=1.0)
        self.paused = True
        self.speed = 1.0
        self.clips: list[DubClip] = []
        self._clip_audio_cache: dict[str, np.ndarray] = {}
        self._lock = threading.Lock()

        self.reanchor_count = 0
        self.last_drift = 0.0
        self._is_ducking = False
        self._stream: Any = None

    def _preload_clip(self, clip: DubClip) -> np.ndarray:
        """Decode and resample audio into memory in worker thread (never in audio callback)."""
        if clip.seg_id in self._clip_audio_cache:
            return self._clip_audio_cache[clip.seg_id]

        if not clip.audio_path.exists():
            return np.zeros(0, dtype=np.float32)

        data, sr = sf.read(str(clip.audio_path))
        if data.ndim > 1:
            data = np.mean(data, axis=1)

        arr_data: np.ndarray = np.asarray(data, dtype=np.float32)

        # Resample to mixer sample rate if different (e.g. Piper 22050 Hz -> 24000 Hz)
        if sr != self.sample_rate and len(arr_data) > 0:
            target_len = round(len(arr_data) * float(self.sample_rate) / float(sr))
            indices = np.linspace(0, len(arr_data) - 1, target_len)
            arr_data = np.interp(indices, np.arange(len(arr_data)), arr_data).astype(np.float32)

        self._clip_audio_cache[clip.seg_id] = arr_data
        return arr_data

    def add_clips(self, new_clips: list[DubClip]) -> None:
        """Add synthesized dub clips to mixer store after pre-decoding."""
        for c in new_clips:
            self._preload_clip(c)
        with self._lock:
            self.clips.extend(new_clips)
            self.clips.sort(key=lambda c: c.start)

    def _get_clip_samples(self, clip: DubClip) -> np.ndarray:
        if clip.seg_id in self._clip_audio_cache:
            return self._clip_audio_cache[clip.seg_id]
        return self._preload_clip(clip)

    def update_anchor(self, player_media_pos: float, speed: float = 1.0) -> None:
        """Update clock anchor from player time-pos notification and correct drift."""
        now = time.monotonic()
        self.speed = speed

        if self.paused:
            self.anchor = ClockAnchor(media_time=player_media_pos, mono_time=now, speed=speed)
            self.last_drift = 0.0
            return

        # Estimate expected media time based on current anchor
        elapsed_mono = now - self.anchor.mono_time
        estimated_media_pos = self.anchor.media_time + (elapsed_mono * self.anchor.speed)
        drift = abs(estimated_media_pos - player_media_pos)
        self.last_drift = drift

        # Re-anchor if drift exceeds threshold (80ms)
        if drift > self.drift_threshold:
            self.reanchor_count += 1
            self.anchor = ClockAnchor(media_time=player_media_pos, mono_time=now, speed=speed)

    def seek(self, target_time: float) -> None:
        """Flush audio buffers and re-anchor clock to target seek time."""
        now = time.monotonic()
        self.anchor = ClockAnchor(media_time=target_time, mono_time=now, speed=self.speed)
        self.last_drift = 0.0

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False
        self.anchor.mono_time = time.monotonic()

    def set_speed(self, speed: float) -> None:
        self.speed = speed
        self.anchor.speed = speed

    def is_ducking_active(self) -> bool:
        return self._is_ducking

    def mix_buffer(self, frames: int, current_mono: float | None = None) -> np.ndarray:
        """Generate next audio output buffer for the PortAudio callback."""
        buffer = np.zeros(frames, dtype=np.float32)

        if self.paused or abs(self.speed - 1.0) > 0.05:
            # Silence if paused or playback speed is not 1.0x
            self._is_ducking = False
            return buffer

        now = current_mono if current_mono is not None else time.monotonic()
        # Compute media time range covered by this buffer
        buffer_duration = frames / float(self.sample_rate)
        media_start = (
            self.anchor.media_time
            + ((now - self.anchor.mono_time) * self.anchor.speed)
            - self.latency_offset_seconds
        )
        media_end = media_start + buffer_duration

        active_dub_in_buffer = False

        # Find overlapping clips using thread-safe snapshot
        with self._lock:
            clips_snapshot = list(self.clips)

        overlapping_clips = [
            c
            for c in clips_snapshot
            if not (c.start + c.duration <= media_start or c.start >= media_end)
        ]

        for clip in overlapping_clips:
            active_dub_in_buffer = True
            clip_samples = self._clip_audio_cache.get(clip.seg_id)
            if clip_samples is None:
                clip_samples = self._get_clip_samples(clip)

            if len(clip_samples) == 0:
                continue

            # Calculate slice bounds within buffer
            clip_sample_offset = round((media_start - clip.start) * self.sample_rate)

            buf_start_idx = 0
            clip_start_idx = clip_sample_offset

            if clip_sample_offset < 0:
                buf_start_idx = -clip_sample_offset
                clip_start_idx = 0

            copy_len = min(
                frames - buf_start_idx,
                len(clip_samples) - clip_start_idx,
            )

            if copy_len > 0 and buf_start_idx < frames and clip_start_idx < len(clip_samples):
                buffer[buf_start_idx : buf_start_idx + copy_len] += clip_samples[
                    clip_start_idx : clip_start_idx + copy_len
                ]

        self._is_ducking = active_dub_in_buffer
        return buffer

    def start_stream(self) -> None:
        """Initialize PortAudio output stream if sounddevice is available."""
        if self._stream is not None:
            return
        try:
            import sounddevice as sd

            def _audio_callback(
                outdata: np.ndarray, frames: int, time_info: Any, status: Any
            ) -> None:
                try:
                    buf = self.mix_buffer(frames)
                    outdata[:] = buf.reshape(-1, 1)
                except Exception:
                    outdata.fill(0.0)

            self._stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                callback=_audio_callback,
            )
            self._stream.start()
        except Exception:
            pass

    def stop_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
