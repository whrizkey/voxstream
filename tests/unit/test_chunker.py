"""Unit tests for chunk planning and silence snapping."""

from voxstream.pipeline.chunker import plan_chunks


def test_plan_chunks_tiling() -> None:
    total_dur = 95.0
    chunks = plan_chunks(total_dur, chunk_seconds=30.0, overlap_seconds=2.0)
    assert len(chunks) == 4

    # Verify cores tile [0, 95] without gaps or overlap
    assert chunks[0].start == 0.0
    assert chunks[0].end == 30.0
    assert chunks[1].start == 30.0
    assert chunks[1].end == 60.0
    assert chunks[2].start == 60.0
    assert chunks[2].end == 90.0
    assert chunks[3].start == 90.0
    assert chunks[3].end == 95.0

    # Verify context padding
    assert chunks[0].pad_before == 0.0
    assert chunks[0].pad_after == 2.0
    assert chunks[1].pad_before == 2.0
    assert chunks[1].pad_after == 2.0
    assert chunks[3].pad_after == 0.0


def test_plan_chunks_silence_snapping() -> None:
    def fake_silence_finder(start: float, end: float) -> float | None:
        # Snap boundary near 30.0 to 28.5
        if 25.0 <= start and end <= 35.0:
            return 28.5
        return None

    chunks = plan_chunks(60.0, chunk_seconds=30.0, silence_finder=fake_silence_finder)
    assert len(chunks) == 2
    assert chunks[0].start == 0.0
    assert chunks[0].end == 28.5
    assert chunks[1].start == 28.5
    assert chunks[1].end == 60.0
