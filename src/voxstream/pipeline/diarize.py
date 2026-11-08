"""Speaker diarization interface and segment attribution."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from voxstream.errors import ExternalToolError
from voxstream.models import Segment


@dataclass(frozen=True)
class SpeakerTurn:
    """A detected time interval spoken by a specific speaker ID."""

    speaker_id: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


class Diarizer(Protocol):
    """Protocol for speaker diarization backends."""

    name: str

    async def diarize(self, audio_path: Path) -> list[SpeakerTurn]:
        """Perform speaker diarization on audio file and return chronological speaker turns."""
        ...


class FakeDiarizer:
    """Deterministic offline diarizer for testing."""

    name: str = "fake_diarizer"

    def __init__(self, turns: list[SpeakerTurn] | None = None) -> None:
        self._turns = turns

    async def diarize(self, audio_path: Path) -> list[SpeakerTurn]:
        if self._turns is not None:
            return sorted(self._turns, key=lambda t: t.start)

        # Default: alternate between SPEAKER_00 and SPEAKER_01 every 3 seconds
        result: list[SpeakerTurn] = []
        for i in range(10):
            start = float(i * 3)
            end = float(start + 3)
            speaker = "SPEAKER_00" if i % 2 == 0 else "SPEAKER_01"
            result.append(SpeakerTurn(speaker_id=speaker, start=start, end=end))
        return result


class PyannoteDiarizer:
    """Speaker diarization using pyannote.audio."""

    name: str = "pyannote"

    def __init__(self, auth_token: str | None = None) -> None:
        self.auth_token = auth_token

    async def diarize(self, audio_path: Path) -> list[SpeakerTurn]:
        import importlib

        try:
            pyannote_mod = importlib.import_module("pyannote.audio")
            pipeline_cls: Any = pyannote_mod.Pipeline
        except ImportError as exc:
            raise ExternalToolError(
                "pyannote.audio is not installed. Install with `pip install pyannote.audio` "
                "and accept the model license terms on HuggingFace."
            ) from exc

        if not self.auth_token:
            raise ExternalToolError(
                "Pyannote diarization requires a HuggingFace authorization token. "
                "Set HUGGINGFACE_TOKEN in your environment or .env."
            )

        try:
            pipeline: Any = pipeline_cls.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.auth_token,
            )
            diarization: Any = pipeline(str(audio_path))
            turns: list[SpeakerTurn] = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                turns.append(
                    SpeakerTurn(
                        speaker_id=str(speaker),
                        start=float(turn.start),
                        end=float(turn.end),
                    )
                )
            return sorted(turns, key=lambda t: t.start)
        except Exception as exc:
            raise ExternalToolError(f"Pyannote diarization failed: {exc}") from exc


def assign_speakers(
    segments: list[Segment],
    turns: list[SpeakerTurn],
) -> list[Segment]:
    """Attribute each Segment to the speaker turn with maximum temporal overlap.

    If a segment does not overlap any speaker turn, attributes it to the nearest turn.
    """
    if not turns or not segments:
        return segments

    sorted_turns = sorted(turns, key=lambda t: t.start)
    assigned: list[Segment] = []

    for seg in segments:
        best_speaker: str | None = None
        max_overlap = 0.0

        for turn in sorted_turns:
            overlap_start = max(seg.start, turn.start)
            overlap_end = min(seg.end, turn.end)
            overlap = max(0.0, overlap_end - overlap_start)
            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = turn.speaker_id

        # If no direct temporal overlap, find the closest turn by midpoint
        if best_speaker is None:
            seg_mid = (seg.start + seg.end) / 2.0
            closest_turn = min(
                sorted_turns,
                key=lambda t: abs(((t.start + t.end) / 2.0) - seg_mid),
            )
            best_speaker = closest_turn.speaker_id

        assigned.append(
            Segment(
                chunk_index=seg.chunk_index,
                seg_id=seg.seg_id,
                start=seg.start,
                end=seg.end,
                text=seg.text,
                language=seg.language,
                speaker=best_speaker,
                confidence=seg.confidence,
            )
        )

    return assigned
