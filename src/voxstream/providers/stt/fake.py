"""Fake deterministic STT provider for offline testing."""

import json
from pathlib import Path

from voxstream.providers.base import RawSegment


class FakeSttProvider:
    name = "fake"

    def __init__(self, fixture_segments: list[RawSegment] | None = None) -> None:
        self.fixture_segments = fixture_segments

    async def transcribe(
        self,
        audio: Path,
        *,
        language: str | None = None,
        word_timestamps: bool = False,
    ) -> list[RawSegment]:
        if self.fixture_segments is not None:
            return self.fixture_segments

        # Look for matching fixture file if exists
        fixture_path = audio.with_suffix(".json")
        if fixture_path.exists():
            try:
                data = json.loads(fixture_path.read_text(encoding="utf-8"))
                return [
                    RawSegment(
                        start=item["start"],
                        end=item["end"],
                        text=item["text"],
                        language=item.get("language", language or "en"),
                        confidence=item.get("confidence", 0.95),
                    )
                    for item in data
                ]
            except Exception:
                pass

        # Default synthetic segments
        return [
            RawSegment(
                start=1.0,
                end=4.0,
                text="Welcome to the video presentation.",
                language=language or "en",
                confidence=0.98,
            ),
            RawSegment(
                start=5.0,
                end=9.5,
                text="Today we discuss real-time speech translation.",
                language=language or "en",
                confidence=0.95,
            ),
            RawSegment(
                start=10.5,
                end=14.0,
                text="Thank you for watching.",
                language=language or "en",
                confidence=0.99,
            ),
        ]
