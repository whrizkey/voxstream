"""Unit tests for dub track timeline rendering and audio ducking."""

import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from voxstream.export.dubtrack import render_dub_track
from voxstream.media.probe import probe_media
from voxstream.models import DubClip


def test_render_dub_track_length_and_ducking() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        clip_wav = tmp_path / "clip.wav"
        output_wav = tmp_path / "rendered_dub.wav"

        # Create 2-second synthesized speech clip at 24000 Hz
        sr = 24000
        clip_dur = 2.0
        data = (
            0.2 * np.sin(2 * np.pi * 400 * np.linspace(0, clip_dur, int(sr * clip_dur)))
        ).astype(np.float32)
        sf.write(str(clip_wav), data, sr)

        clip = DubClip(
            seg_id="c1",
            start=1.0,
            audio_path=clip_wav,
            duration=clip_dur,
            speed_factor=1.0,
            overflow=0.0,
        )

        total_dur = 6.0
        render_dub_track(
            clips=[clip],
            total_duration=total_dur,
            output_wav=output_wav,
            sample_rate=sr,
            duck_db=-14.0,
        )

        assert output_wav.exists()
        probe = probe_media(output_wav)
        # Length equals total_duration within 20ms tolerance
        assert abs(probe.duration - total_dur) < 0.02
