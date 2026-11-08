"""Property-based unit tests for the pure time-fitting algorithm."""

from hypothesis import given
from hypothesis import strategies as st

from voxstream.pipeline.fit import fit_clip


@given(
    seg_start=st.floats(min_value=0.0, max_value=500.0),
    slot=st.floats(min_value=0.5, max_value=15.0),
    gap=st.floats(min_value=0.0, max_value=5.0),
    clip_dur=st.floats(min_value=0.2, max_value=25.0),
    max_speedup=st.floats(min_value=1.1, max_value=1.5),
)
def test_fit_clip_properties(
    seg_start: float,
    slot: float,
    gap: float,
    clip_dur: float,
    max_speedup: float,
) -> None:
    seg_end = seg_start + slot
    next_start = seg_end + gap

    decision = fit_clip(
        seg_start=seg_start,
        seg_end=seg_end,
        next_seg_start=next_start,
        clip_duration=clip_dur,
        max_speedup=max_speedup,
        allow_retranslation=False,
    )

    # 1. Effective duration never exceeds room
    room = max(slot, min(next_start - seg_start, slot + 1.0))
    assert decision.effective_duration <= room + 1e-4

    # 2. Speed factor is within valid bounds
    assert decision.speed_factor >= 1.0
    assert decision.speed_factor <= (max_speedup * 1.1) + 1e-4

    # 3. Truncation flag only set when speedup hit max limit and duration still exceeded room
    if "truncated" in decision.flags:
        assert decision.speed_factor >= max_speedup
        assert "stretched" in decision.flags
