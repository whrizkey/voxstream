"""Unit tests for core data models."""

from pathlib import Path

from voxstream.models import ChunkSpec, DubClip, MediaInfo, Segment, TranslatedSegment


def test_media_info_creation() -> None:
    info = MediaInfo(
        media_id="test1234",
        path_or_url="/tmp/video.mp4",
        duration=120.5,
        has_audio=True,
    )
    assert info.media_id == "test1234"
    assert info.duration == 120.5
    assert info.has_audio is True


def test_chunk_spec_calculations() -> None:
    chunk = ChunkSpec(
        index=0,
        start=0.0,
        end=30.0,
        pad_before=2.0,
        pad_after=2.0,
    )
    assert chunk.core_duration == 30.0
    assert chunk.extraction_start == 0.0
    assert chunk.extraction_duration == 32.0

    chunk_mid = ChunkSpec(
        index=1,
        start=30.0,
        end=60.0,
        pad_before=2.0,
        pad_after=2.0,
    )
    assert chunk_mid.extraction_start == 28.0
    assert chunk_mid.extraction_duration == 34.0


def test_segment_midpoint_calculation() -> None:
    seg = Segment(
        chunk_index=0,
        seg_id="seg_001",
        start=10.0,
        end=14.0,
        text="Hello world",
        language="en",
    )
    assert seg.duration == 4.0
    assert seg.midpoint == 12.0


def test_dub_clip_properties() -> None:
    clip = DubClip(
        seg_id="seg_001",
        start=10.0,
        audio_path=Path("/tmp/clip.wav"),
        duration=3.8,
        speed_factor=1.0,
        overflow=0.0,
        flags=frozenset(["stretched"]),
    )
    assert clip.speed_factor == 1.0
    assert "stretched" in clip.flags


def test_translated_segment_creation() -> None:
    seg = Segment(
        chunk_index=0,
        seg_id="seg_001",
        start=1.0,
        end=3.0,
        text="Hello",
        language="en",
    )
    trans = TranslatedSegment(
        seg=seg,
        target_lang="es",
        text="Hola",
        provider="fake",
    )
    assert trans.target_lang == "es"
    assert trans.text == "Hola"
    assert trans.seg.start == 1.0
