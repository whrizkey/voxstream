"""Core domain models and immutable data contracts."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class ChunkState(StrEnum):
    """Lifecycle states of an audio chunk through the processing pipeline."""

    PENDING = "PENDING"
    TRANSCRIBED = "TRANSCRIBED"
    TRANSLATED = "TRANSLATED"
    SYNTHESIZED = "SYNTHESIZED"
    READY = "READY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class MediaInfo:
    """Information discovered from media probing."""

    media_id: str
    path_or_url: str
    duration: float
    has_audio: bool


@dataclass(frozen=True)
class ChunkSpec:
    """Specification of an audio processing chunk with boundary padding."""

    index: int
    start: float
    end: float
    pad_before: float
    pad_after: float

    @property
    def core_duration(self) -> float:
        return self.end - self.start

    @property
    def extraction_start(self) -> float:
        return max(0.0, self.start - self.pad_before)

    @property
    def extraction_duration(self) -> float:
        return (self.end + self.pad_after) - self.extraction_start


@dataclass(frozen=True)
class Segment:
    """An individual spoken utterance produced by Speech-to-Text."""

    chunk_index: int
    seg_id: str
    start: float
    end: float
    text: str
    language: str
    speaker: str | None = None
    confidence: float | None = None

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def midpoint(self) -> float:
        return (self.start + self.end) / 2.0


@dataclass(frozen=True)
class TranslatedSegment:
    """A segment translated into a specific target language."""

    seg: Segment
    target_lang: str
    text: str
    provider: str


@dataclass(frozen=True)
class DubClip:
    """A synthesized audio dub clip fitted to timeline constraints."""

    seg_id: str
    start: float
    audio_path: Path
    duration: float
    speed_factor: float = 1.0
    overflow: float = 0.0
    flags: frozenset[str] = field(default_factory=frozenset)
