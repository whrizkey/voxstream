"""Unit tests for DubMixer clock synchronization, drift correction, and speed limits."""

import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from voxstream.models import DubClip
from voxstream.playback.mixer import DubMixer


def test_mixer_drift_detection_and_reanchor() -> None:
    mixer = DubMixer(sample_rate=24000, drift_threshold=0.08)
    mixer.resume()

    # Anchor at t=0.0s
    mixer.update_anchor(0.0)
    assert mixer.reanchor_count == 0

    # Normal update within threshold (10ms drift)
    mixer.update_anchor(0.01)
    assert mixer.reanchor_count == 0

    # Big sudden jump (150ms drift) -> triggers re-anchor!
    mixer.update_anchor(0.5)
    assert mixer.reanchor_count == 1
    assert mixer.anchor.media_time == 0.5


def test_mixer_speed_limitation_mutes_dub() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        clip_path = Path(tmp_dir) / "clip.wav"
        sr = 24000
        sf.write(str(clip_path), np.ones(24000, dtype=np.float32), sr)

        clip = DubClip(
            seg_id="c1",
            start=0.0,
            audio_path=clip_path,
            duration=1.0,
            speed_factor=1.0,
            overflow=0.0,
        )
        mixer = DubMixer(sample_rate=sr)
        mixer.add_clips([clip])
        mixer.resume()
        mixer.update_anchor(0.0)

        # 1. At 1.0x speed -> audio is mixed
        buf_normal = mixer.mix_buffer(1024)
        assert np.any(buf_normal > 0)
        assert mixer.is_ducking_active() is True

        # 2. At 1.25x speed -> dub is muted (silence)
        mixer.set_speed(1.25)
        buf_fast = mixer.mix_buffer(1024)
        assert np.all(buf_fast == 0.0)
        assert mixer.is_ducking_active() is False

        # 3. Returning to 1.0x -> dub is restored
        mixer.set_speed(1.0)
        buf_restored = mixer.mix_buffer(1024)
        assert np.any(buf_restored > 0)
