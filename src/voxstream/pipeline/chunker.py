"""Audio timeline chunk planning with silence snapping."""

from collections.abc import Callable

from voxstream.models import ChunkSpec


def plan_chunks(
    total_duration: float,
    chunk_seconds: float = 30.0,
    overlap_seconds: float = 2.0,
    silence_finder: Callable[[float, float], float | None] | None = None,
) -> list[ChunkSpec]:
    """Plan non-overlapping chunk cores tiling total_duration with context overlap padding."""
    if total_duration <= 0.0:
        return []

    # 1. Nominal boundaries: 0, 30, 60, ..., duration
    boundaries: list[float] = [0.0]
    curr = chunk_seconds
    while curr < total_duration:
        # Check silence snapping if finder provided
        snapped = curr
        if silence_finder is not None:
            candidate = silence_finder(curr - 5.0, curr + 5.0)
            if candidate is not None and 0.0 < candidate < total_duration:
                snapped = candidate
        boundaries.append(snapped)
        curr += chunk_seconds

    boundaries.append(total_duration)
    # Ensure strictly increasing
    boundaries = sorted(set(boundaries))

    chunks: list[ChunkSpec] = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        pad_before = min(overlap_seconds, start)
        pad_after = min(overlap_seconds, total_duration - end)

        chunks.append(
            ChunkSpec(
                index=i,
                start=start,
                end=end,
                pad_before=pad_before,
                pad_after=pad_after,
            )
        )

    return chunks
