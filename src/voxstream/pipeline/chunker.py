"""Audio timeline chunk planning with silence snapping."""

from collections.abc import Callable
from pathlib import Path

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


def create_silence_finder(
    media_path: str | Path,
) -> Callable[[float, float], float | None] | None:
    """Create a silence snapping callback for chunk boundaries using audio RMS analysis."""
    target_path = Path(media_path)
    if not target_path.is_file():
        return None

    try:
        import numpy as np
        import soundfile as sf

        info = sf.info(str(target_path))
        sr = int(info.samplerate)

        def _soundfile_finder(window_start: float, window_end: float) -> float | None:
            try:
                start_frame = max(0, int(window_start * sr))
                frames_to_read = max(1, int((window_end - window_start) * sr))
                data, _ = sf.read(str(target_path), start=start_frame, frames=frames_to_read)
                if data.ndim > 1:
                    data = np.mean(data, axis=1)
                if len(data) == 0:
                    return None

                block_size = max(1, int(sr * 0.1))
                num_blocks = len(data) // block_size
                if num_blocks == 0:
                    return None

                min_rms = float("inf")
                best_t: float | None = None
                for b in range(num_blocks):
                    block = data[b * block_size : (b + 1) * block_size]
                    rms = float(np.sqrt(np.mean(block**2)))
                    if rms < min_rms:
                        min_rms = rms
                        best_t = window_start + (b + 0.5) * 0.1

                return best_t
            except Exception:
                return None

        return _soundfile_finder
    except Exception:
        return None
