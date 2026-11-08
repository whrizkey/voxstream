"""Unit tests for media probing, fingerprinting, and extraction."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from voxstream.errors import MediaError
from voxstream.media.extract import extract_audio_chunk
from voxstream.media.fingerprint import calculate_fingerprint
from voxstream.media.probe import probe_media


@pytest.fixture
def sample_audio_wav() -> Generator[Path, None, None]:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    sr = 16000
    duration = 3.0
    num_samples = int(sr * duration)
    data = 0.1 * np.sin(2 * np.pi * 440 * np.linspace(0, duration, num_samples)).astype(np.float32)
    sf.write(str(tmp_path), data, sr)
    yield tmp_path
    if tmp_path.exists():
        tmp_path.unlink(missing_ok=True)


def test_probe_media_audio(sample_audio_wav: Path) -> None:
    probe = probe_media(sample_audio_wav)
    assert probe.has_audio is True
    assert probe.duration > 2.8 and probe.duration < 3.2
    assert probe.audio_sample_rate == 16000
    assert probe.audio_channels == 1


def test_probe_missing_file() -> None:
    with pytest.raises(MediaError, match="does not exist"):
        probe_media("/tmp/definitely_missing_file_xyz.mp4")


def test_calculate_fingerprint(sample_audio_wav: Path) -> None:
    fp1 = calculate_fingerprint(sample_audio_wav, duration=3.0)
    fp2 = calculate_fingerprint(sample_audio_wav, duration=3.0)
    assert fp1 == fp2
    assert len(fp1) == 32

    # Different duration alters the fingerprint
    fp_diff = calculate_fingerprint(sample_audio_wav, duration=4.0)
    assert fp1 != fp_diff


def test_extract_audio_chunk(sample_audio_wav: Path) -> None:
    out_tmp = sample_audio_wav.with_name("extracted.wav")
    try:
        extract_audio_chunk(
            sample_audio_wav,
            out_tmp,
            start_seconds=0.5,
            duration_seconds=1.5,
            sample_rate=16000,
        )
        assert out_tmp.exists()
        probe = probe_media(out_tmp)
        assert abs(probe.duration - 1.5) < 0.1
    finally:
        if out_tmp.exists():
            out_tmp.unlink(missing_ok=True)
