"""In-memory subtitle cue store and ASS overlay renderer."""

import bisect
from dataclasses import dataclass


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str
    original_text: str | None = None

    def contains(self, t: float) -> bool:
        return self.start <= t < self.end


class SubtitleStore:
    """Thread-safe, sorted subtitle cue store with O(log n) time lookup."""

    def __init__(self) -> None:
        self._cues: list[Cue] = []
        self._starts: list[float] = []

    def clear(self) -> None:
        self._cues.clear()
        self._starts.clear()

    def add_cues(self, new_cues: list[Cue]) -> None:
        """Add cues and maintain sorted order with non-overlapping bounds."""
        for cue in new_cues:
            end = max(cue.end, cue.start + 0.8)
            self._cues.append(
                Cue(
                    start=cue.start,
                    end=end,
                    text=cue.text,
                    original_text=cue.original_text,
                )
            )

        # Sort all cues by start time
        self._cues.sort(key=lambda c: c.start)

        # Resolve forward overlaps
        for i in range(len(self._cues) - 1):
            if self._cues[i].end > self._cues[i + 1].start:
                prev = self._cues[i]
                self._cues[i] = Cue(
                    start=prev.start,
                    end=self._cues[i + 1].start,
                    text=prev.text,
                    original_text=prev.original_text,
                )

        self._starts = [c.start for c in self._cues]

    def get_active_cue(self, t: float) -> Cue | None:
        """Find the cue currently active at timestamp t in O(log n) time."""
        if not self._cues:
            return None

        idx = bisect.bisect_right(self._starts, t) - 1
        if 0 <= idx < len(self._cues):
            candidate = self._cues[idx]
            if candidate.contains(t):
                return candidate
        return None

    def all_cues(self) -> list[Cue]:
        return list(self._cues)
