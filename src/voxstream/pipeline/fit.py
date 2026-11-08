"""Pure time-fitting algorithm for aligning synthesized speech clips with video timestamps."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FitDecision:
    speed_factor: float
    overflow: float
    effective_duration: float
    needs_retranslation: bool
    scale_factor: float = 1.0
    flags: frozenset[str] = field(default_factory=frozenset)


def fit_clip(
    seg_start: float,
    seg_end: float,
    next_seg_start: float | None,
    clip_duration: float,
    max_speedup: float = 1.25,
    allow_retranslation: bool = True,
) -> FitDecision:
    """Calculate speedup, gap overflow, and truncation decisions for an utterance.

    Guarantees:
    - Clip start is never moved earlier or later than seg_start.
    - Effective clip end never exceeds room (min(next_seg_start, seg_start + slot + 1.0)).
    - Speedup factor never exceeds max_speedup * 1.1.
    """
    slot = max(0.1, seg_end - seg_start)

    if next_seg_start is not None and next_seg_start > seg_start:
        available_gap = next_seg_start - seg_start
        room = min(available_gap, slot + 1.0)
    else:
        room = slot + 1.0

    # Room must at least accommodate slot
    room = max(slot, room)

    # 1. Exact fit within original speech slot
    if clip_duration <= slot:
        return FitDecision(
            speed_factor=1.0,
            overflow=0.0,
            effective_duration=clip_duration,
            needs_retranslation=False,
            flags=frozenset(),
        )

    # 2. Fits within natural trailing silence gap without speedup
    if clip_duration <= room:
        overflow = clip_duration - slot
        return FitDecision(
            speed_factor=1.0,
            overflow=overflow,
            effective_duration=clip_duration,
            needs_retranslation=False,
            flags=frozenset(),
        )

    # 3. Clip exceeds allowable room: check required speedup
    needed_speedup = clip_duration / room

    if needed_speedup <= max_speedup:
        return FitDecision(
            speed_factor=needed_speedup,
            overflow=room - slot,
            effective_duration=room,
            needs_retranslation=False,
            flags=frozenset(["stretched"]),
        )

    # 4. Overflow exceeds max_speedup: request retranslation with tighter character budget
    if allow_retranslation:
        scale = 1.0 / needed_speedup
        return FitDecision(
            speed_factor=1.0,
            overflow=room - slot,
            effective_duration=room,
            needs_retranslation=True,
            scale_factor=scale,
            flags=frozenset(["retranslation_requested"]),
        )

    # 5. Fallback after retranslation: stretch up to max_speedup * 1.1, then truncate
    stretched_limit_speed = max_speedup * 1.1
    duration_at_max_stretch = clip_duration / stretched_limit_speed

    if duration_at_max_stretch <= room:
        effective = duration_at_max_stretch
        flags = frozenset(["stretched"])
    else:
        effective = room
        flags = frozenset(["stretched", "truncated"])

    return FitDecision(
        speed_factor=stretched_limit_speed,
        overflow=max(0.0, effective - slot),
        effective_duration=effective,
        needs_retranslation=False,
        flags=flags,
    )
