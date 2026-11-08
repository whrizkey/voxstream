"""Integration tests for live dubbing synchronization, drift bounds, and seek resilience."""

import random
import tempfile
from collections.abc import Generator
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from voxstream.playback.controller import PlaybackController
from voxstream.playback.player import VirtualPlayer
from voxstream.providers.stt.fake import FakeSttProvider
from voxstream.providers.translate.fake import FakeTranslateProvider
from voxstream.providers.tts.fake import FakeTtsProvider


@pytest.fixture
def dub_sample_wav() -> Generator[Path, None, None]:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    sr = 16000
    duration = 60.0
    num_samples = int(sr * duration)
    data = (0.05 * np.sin(2 * np.pi * 300 * np.linspace(0, duration, num_samples))).astype(
        np.float32
    )
    sf.write(str(tmp_path), data, sr)
    yield tmp_path
    if tmp_path.exists():
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_live_dubbing_timing_and_seek_drift(dub_sample_wav: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_dir = Path(tmp_dir) / "cache"
        player = VirtualPlayer(duration=60.0)

        controller = PlaybackController(
            media_path=dub_sample_wav,
            target_lang="es",
            mode="both",
            player=player,
            stt_provider=FakeSttProvider(),
            translate_provider=FakeTranslateProvider(),
            tts_provider=FakeTtsProvider(),
            cache_dir=cache_dir,
        )

        # Pre-buffer initial state
        await controller.step()
        controller.play()

        # Perform 10 random seeks and assert drift stays bounded within 80ms
        random.seed(123)
        for _ in range(10):
            target = random.uniform(0.0, 50.0)
            controller.seek(target)
            # Re-anchor
            controller.mixer.update_anchor(target)
            assert controller.mixer.last_drift <= 0.08
            # Buffer audio output
            buf = controller.mixer.mix_buffer(512)
            assert len(buf) == 512
