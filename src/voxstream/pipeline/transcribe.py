"""Stage 1: Transcription with boundary de-duplication and text normalization."""

import re
from pathlib import Path

from voxstream.models import ChunkSpec, Segment
from voxstream.providers.base import RawSegment, SttProvider

# Known repetitive filler / hallucination patterns from Whisper on silence/music
KNOWN_HALLUCINATIONS = {
    "thank you.",
    "thanks for watching.",
    "subtitles by",
    "please subscribe",
    "bye.",
    "you",
}


def deduplicate_and_clean_segments(
    raw_segments: list[RawSegment],
    chunk: ChunkSpec,
    media_id: str,
) -> list[Segment]:
    """Filter raw segments to those owned by the chunk core using midpoint assignment."""
    chunk_audio_start = chunk.extraction_start
    cleaned: list[Segment] = []

    for raw in raw_segments:
        # Convert to media absolute time
        abs_start = chunk_audio_start + raw.start
        abs_end = chunk_audio_start + raw.end
        midpoint = (abs_start + abs_end) / 2.0

        # Boundary de-duplication: strictly check if midpoint lies in chunk core [start, end)
        if not (chunk.start <= midpoint < chunk.end):
            continue

        text = raw.text.strip()
        text = re.sub(r"\s+", " ", text)
        if not text:
            continue

        lower = text.lower().rstrip(".!?")
        if lower in KNOWN_HALLUCINATIONS and (raw.confidence is not None and raw.confidence < 0.3):
            continue

        seg_id = f"{media_id}:{round(abs_start * 1000)}:{round(abs_end * 1000)}"
        cleaned.append(
            Segment(
                chunk_index=chunk.index,
                seg_id=seg_id,
                start=abs_start,
                end=abs_end,
                text=text,
                language=raw.language,
                confidence=raw.confidence,
            )
        )

    # Merge very short adjacent segments (<0.6s, gap <0.2s)
    merged: list[Segment] = []
    i = 0
    while i < len(cleaned):
        curr = cleaned[i]
        if i + 1 < len(cleaned):
            nxt = cleaned[i + 1]
            gap = nxt.start - curr.end
            dur = curr.end - curr.start
            if dur < 0.6 and 0.0 <= gap < 0.2:
                # Merge curr and nxt
                merged_text = f"{curr.text} {nxt.text}"
                merged_id = f"{media_id}:{round(curr.start * 1000)}:{round(nxt.end * 1000)}"
                curr = Segment(
                    chunk_index=curr.chunk_index,
                    seg_id=merged_id,
                    start=curr.start,
                    end=nxt.end,
                    text=merged_text,
                    language=curr.language,
                    confidence=min(curr.confidence or 1.0, nxt.confidence or 1.0),
                )
                i += 1
        merged.append(curr)
        i += 1

    return merged


async def transcribe_chunk(
    stt_provider: SttProvider,
    audio_path: Path,
    chunk: ChunkSpec,
    media_id: str,
    language: str | None = None,
) -> list[Segment]:
    """Transcribe chunk audio and clean/deduplicate segments into media timeline coordinates."""
    raw_segments = await stt_provider.transcribe(audio_path, language=language)
    return deduplicate_and_clean_segments(raw_segments, chunk, media_id)
