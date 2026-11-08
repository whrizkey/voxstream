"""Integration test for offline batch subtitle generation and cache hits."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from voxstream.pipeline.batch import process_media_offline
from voxstream.providers.stt.fake import FakeSttProvider
from voxstream.providers.translate.fake import FakeTranslateProvider


@pytest.fixture
def test_video_wav() -> Generator[Path, None, None]:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    # 35 seconds of audio so it creates 2 chunks with 30s chunk_seconds
    sr = 16000
    duration = 35.0
    num_samples = int(sr * duration)
    data = (0.05 * np.sin(2 * np.pi * 300 * np.linspace(0, duration, num_samples))).astype(
        np.float32
    )
    sf.write(str(tmp_path), data, sr)
    yield tmp_path
    if tmp_path.exists():
        tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_batch_offline_subtitles_and_cache(test_video_wav: Path) -> None:
    with tempfile.TemporaryDirectory() as out_dir_str:
        out_dir = Path(out_dir_str)

        # Run 1: Cold run
        test_cache_dir = out_dir / "cache"
        stt = FakeSttProvider()
        tr = FakeTranslateProvider()
        stats1 = await process_media_offline(
            input_path=test_video_wav,
            target_lang="es",
            output_dir=out_dir,
            mode="subs",
            cache_dir=test_cache_dir,
            stt_provider=stt,
            translate_provider=tr,
        )

        assert stats1["total_chunks"] == 2
        assert stats1["cache_hits"] == 0
        assert stats1["total_segments"] > 0
        srt_file = stats1["srt_path"]
        assert srt_file.exists()
        srt_content = srt_file.read_text(encoding="utf-8")
        assert "-->" in srt_content
        assert "[es]" in srt_content

        # Run 2: Warm run (all chunks cached)
        stats2 = await process_media_offline(
            input_path=test_video_wav,
            target_lang="es",
            output_dir=out_dir,
            mode="subs",
            cache_dir=test_cache_dir,
            stt_provider=stt,
            translate_provider=tr,
        )

        assert stats2["total_chunks"] == 2
        assert stats2["cache_hits"] == 2  # 100% cache hits!
        assert stats2["total_segments"] == stats1["total_segments"]
