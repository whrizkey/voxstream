"""Unit tests for transcribe stage and midpoint de-duplication."""

from voxstream.models import ChunkSpec
from voxstream.pipeline.transcribe import deduplicate_and_clean_segments
from voxstream.providers.base import RawSegment


def test_boundary_midpoint_deduplication() -> None:
    # Chunk 0: core [0, 30], extracted [0, 32]
    chunk0 = ChunkSpec(index=0, start=0.0, end=30.0, pad_before=0.0, pad_after=2.0)
    # Chunk 1: core [30, 60], extracted [28, 62]
    chunk1 = ChunkSpec(index=1, start=30.0, end=60.0, pad_before=2.0, pad_after=2.0)

    # Segment straddling the boundary: start=29.0, end=31.5 (media-absolute)
    # Midpoint = 30.25 -> Belongs to chunk 1!
    # In chunk 0: relative to 0.0 -> start=29.0, end=31.5
    raw0 = [
        RawSegment(start=10.0, end=15.0, text="First utterance", language="en"),
        RawSegment(start=29.0, end=31.5, text="Straddling utterance", language="en"),
    ]
    # In chunk 1: relative to extraction_start 28.0:
    # Start = 29.0 - 28.0 = 1.0, End = 31.5 - 28.0 = 3.5
    raw1 = [
        RawSegment(start=1.0, end=3.5, text="Straddling utterance", language="en"),
        RawSegment(start=12.0, end=18.0, text="Later utterance", language="en"),
    ]

    segs0 = deduplicate_and_clean_segments(raw0, chunk0, "media1")
    segs1 = deduplicate_and_clean_segments(raw1, chunk1, "media1")

    # The straddling utterance should be dropped from chunk 0 because midpoint (30.25) >= 30.0
    texts0 = [s.text for s in segs0]
    assert texts0 == ["First utterance"]

    # The straddling utterance MUST be present in chunk 1
    texts1 = [s.text for s in segs1]
    assert "Straddling utterance" in texts1
    assert "Later utterance" in texts1


def test_short_segment_merging() -> None:
    chunk = ChunkSpec(index=0, start=0.0, end=30.0, pad_before=0.0, pad_after=0.0)
    # Two short segments close together
    raw = [
        RawSegment(start=1.0, end=1.4, text="Wait", language="en"),
        RawSegment(start=1.5, end=2.0, text="a minute.", language="en"),
    ]
    segs = deduplicate_and_clean_segments(raw, chunk, "media1")
    assert len(segs) == 1
    assert segs[0].text == "Wait a minute."
    assert segs[0].start == 1.0
    assert segs[0].end == 2.0
