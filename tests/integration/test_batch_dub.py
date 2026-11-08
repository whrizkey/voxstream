"""Integration test for offline dubbing pipeline and media muxing."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from voxstream.media.probe import probe_media
from voxstream.pipeline.batch import process_media_offline
from voxstream.providers.stt.fake import FakeSttProvider
from voxstream.providers.translate.fake import FakeTranslateProvider
from voxstream.providers.tts.fake import FakeTtsProvider


@pytest.fixture
def synthetic_video_wav() -> Generator[Path, None, None]:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    # 15 seconds of audio
    sr = 16000
    duration = 15.0
    num_samples = int(sr * duration)
    data = (0.05 * np.sin(2 * np.pi * 300 * np.linspace(0, duration, num_samples))).astype(
        np.float32
    )
    sf.write(str(tmp_path), data, sr)
    yield tmp_path
    if tmp_path.exists():
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_batch_offline_dubbing_and_muxing(synthetic_video_wav: Path) -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as out_dir_str:
        out_dir = Path(out_dir_str)

        stats = await process_media_offline(
            input_path=synthetic_video_wav,
            target_lang="es",
            output_dir=out_dir,
            mode="both",
            mux=True,
            cache_dir=out_dir / "cache",
            stt_provider=FakeSttProvider(),
            translate_provider=FakeTranslateProvider(),
            tts_provider=FakeTtsProvider(),
        )

        assert stats["total_segments"] > 0
        assert stats["total_clips"] > 0

        # Subtitle output
        srt_file = stats["srt_path"]
        assert srt_file.exists()

        # Dub audio output
        dub_file = stats["dub_wav_path"]
        assert dub_file is not None
        assert dub_file.exists()
        probe_dub = probe_media(dub_file)
        assert abs(probe_dub.duration - stats["duration"]) < 0.05

        # Muxed output
        muxed_file = stats["muxed_path"]
        assert muxed_file is not None
        assert muxed_file.exists()
        probe_muxed = probe_media(muxed_file)
        assert probe_muxed.has_audio is True
