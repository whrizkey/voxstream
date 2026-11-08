"""Unit tests for LookaheadScheduler generation counter and seek handling."""

import tempfile
from pathlib import Path

import pytest

from voxstream.models import ChunkSpec, ChunkState
from voxstream.pipeline.cache import CacheManager
from voxstream.pipeline.scheduler import LookaheadScheduler
from voxstream.providers.stt.fake import FakeSttProvider
from voxstream.providers.translate.fake import FakeTranslateProvider


@pytest.mark.asyncio
async def test_scheduler_seek_increments_generation() -> None:
    chunks = [
        ChunkSpec(index=0, start=0.0, end=30.0, pad_before=0.0, pad_after=2.0),
        ChunkSpec(index=1, start=30.0, end=60.0, pad_before=2.0, pad_after=2.0),
    ]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        cache = CacheManager(Path(tmp_dir))
        scheduler = LookaheadScheduler(
            playhead_fn=lambda: 0.0,
            chunks=chunks,
            media_id="0123456789abcdef0123456789abcdef",
            media_path=Path("/dummy.wav"),
            cache=cache,
            stt_provider=FakeSttProvider(),
            translate_provider=FakeTranslateProvider(),
            target_lang="es",
        )

        assert scheduler.generation == 0
        scheduler.on_seek(45.0)
        assert scheduler.generation == 1
        scheduler.on_seek(10.0)
        assert scheduler.generation == 2


@pytest.mark.asyncio
async def test_scheduler_buffering_notifications() -> None:
    chunks = [
        ChunkSpec(index=0, start=0.0, end=30.0, pad_before=0.0, pad_after=2.0),
        ChunkSpec(index=1, start=30.0, end=60.0, pad_before=2.0, pad_after=2.0),
    ]
    buffering_events: list[bool] = []

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        cache = CacheManager(Path(tmp_dir))
        scheduler = LookaheadScheduler(
            playhead_fn=lambda: 0.0,
            chunks=chunks,
            media_id="0123456789abcdef0123456789abcdef",
            media_path=Path("/dummy.wav"),
            cache=cache,
            stt_provider=FakeSttProvider(),
            translate_provider=FakeTranslateProvider(),
            target_lang="es",
        )
        scheduler.register_buffering_callback(lambda b: buffering_events.append(b))

        # Chunk 0 is pending -> underrun triggers buffering True
        scheduler._check_underrun(5.0)
        assert buffering_events == [True]

        # Once chunk 0 is ready -> buffering turns False
        scheduler.chunk_states[0] = ChunkState.READY
        scheduler._check_underrun(5.0)
        assert buffering_events == [True, False]


@pytest.mark.asyncio
async def test_scheduler_stuck_chunk_retry_after_seek(sample_wav: Path) -> None:
    chunks = [
        ChunkSpec(index=0, start=0.0, end=5.0, pad_before=0.0, pad_after=0.5),
    ]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        cache = CacheManager(Path(tmp_dir))
        scheduler = LookaheadScheduler(
            playhead_fn=lambda: 1.0,
            chunks=chunks,
            media_id="0123456789abcdef0123456789abcdef",
            media_path=sample_wav,
            cache=cache,
            stt_provider=FakeSttProvider(),
            translate_provider=FakeTranslateProvider(),
            target_lang="es",
            lookahead_seconds=10.0,
        )
        # Simulate chunk stuck in TRANSCRIBED state due to generation bump on seek
        scheduler.chunk_states[0] = ChunkState.TRANSCRIBED
        scheduler.generation = 1

        # step() should re-schedule and advance it to READY
        await scheduler.step()
        assert scheduler.chunk_states[0] == ChunkState.READY
