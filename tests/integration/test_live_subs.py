"""Integration tests for live lookahead subtitles, seek storms, and underrun buffering."""

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


@pytest.fixture
def long_sample_wav() -> Generator[Path, None, None]:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    # 120 seconds of audio
    sr = 16000
    duration = 120.0
    num_samples = int(sr * duration)
    data = (0.05 * np.sin(2 * np.pi * 300 * np.linspace(0, duration, num_samples))).astype(
        np.float32
    )
    sf.write(str(tmp_path), data, sr)
    yield tmp_path
    if tmp_path.exists():
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_live_seek_storm(long_sample_wav: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_dir = Path(tmp_dir) / "cache"
        player = VirtualPlayer(duration=120.0)

        controller = PlaybackController(
            media_path=long_sample_wav,
            target_lang="es",
            player=player,
            stt_provider=FakeSttProvider(),
            translate_provider=FakeTranslateProvider(),
            cache_dir=cache_dir,
        )

        # Pre-buffer initial state
        await controller.step()

        # Execute 20 random seeks
        random.seed(42)
        for _ in range(20):
            target = random.uniform(0.0, 110.0)
            controller.seek(target)
            assert abs(player.get_time_pos() - target) < 0.05
            # Step the scheduler at the new position
            await controller.step()
            # If the chunk was processed, subtitle lookup works without crash
            _ = controller.get_active_subtitle()

        # Cache remains healthy
        stats = controller.cache.get_stats()
        assert stats["media_count"] >= 1


@pytest.mark.asyncio
async def test_live_underrun_pauses_and_resumes(long_sample_wav: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_dir = Path(tmp_dir) / "cache"
        player = VirtualPlayer(duration=120.0)
        player.play()

        controller = PlaybackController(
            media_path=long_sample_wav,
            target_lang="es",
            player=player,
            stt_provider=FakeSttProvider(),
            translate_provider=FakeTranslateProvider(),
            cache_dir=cache_dir,
        )

        # Jump far ahead to unbuffered chunk at 95.0s
        controller.seek(95.0)
        assert controller.is_buffering is True
        assert player.is_paused() is True

        # Run scheduler step to process the unbuffered chunk
        await controller.step()

        # Once ready, buffering clears and player resumes automatically
        assert controller.is_buffering is False
        assert player.is_paused() is False
