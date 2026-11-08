"""Abstract protocols and data items for STT, Translation, and TTS providers."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RawSegment:
    """Raw transcription segment relative to chunk audio file start."""

    start: float
    end: float
    text: str
    language: str
    confidence: float | None = None


@dataclass(frozen=True)
class TranslateItem:
    """Unit of text to be translated with optional timing and character constraints."""

    id: str
    text: str
    max_chars: int | None = None
    duration: float | None = None


@dataclass(frozen=True)
class TranslateResult:
    """Translated output matching a TranslateItem ID."""

    id: str
    text: str


@dataclass(frozen=True)
class Voice:
    """Text-to-speech voice specification."""

    id: str
    name: str
    lang: str
    gender: str | None = None


@runtime_checkable
class SttProvider(Protocol):
    """Protocol for Speech-to-Text transcription engines."""

    name: str

    async def transcribe(
        self,
        audio: Path,
        *,
        language: str | None = None,
        word_timestamps: bool = False,
    ) -> list[RawSegment]:
        """Transcribe an audio file into raw timestamped segments."""
        ...


@runtime_checkable
class TranslateProvider(Protocol):
    """Protocol for language translation engines."""

    name: str

    async def translate(
        self,
        items: list[TranslateItem],
        *,
        source_lang: str | None,
        target_lang: str,
        context: list[str],
    ) -> list[TranslateResult]:
        """Translate a batch of text items respecting constraints and context."""
        ...


@runtime_checkable
class TtsProvider(Protocol):
    """Protocol for Text-to-Speech synthesis engines."""

    name: str
    sample_rate: int

    def list_voices(self, lang: str) -> list[Voice]:
        """List available voices for a language code."""
        ...

    async def synthesize(
        self,
        text: str,
        *,
        lang: str,
        voice: str | None = None,
        rate: float = 1.0,
    ) -> Path:
        """Synthesize text into a WAV file and return its path."""
        ...


# Secret redaction patterns (e.g. sk-..., key-..., bearer tokens)
_SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}"),
    re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
    re.compile(r"(api[_-]?key\s*[:=]\s*['\"]?)[a-zA-Z0-9_\-]{16,}(['\"]?)", re.IGNORECASE),
]


def redact_secrets(message: str) -> str:
    """Mask known API keys and tokens in log messages and error output."""
    redacted = message
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted
