"""SubRip (.srt) subtitle formatting and export."""

import textwrap
from pathlib import Path

from voxstream.models import TranslatedSegment


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds into standard SubRip timestamp (HH:MM:SS,mmm)."""
    total_ms = max(0, round(seconds * 1000.0))
    ms = total_ms % 1000
    total_sec = total_ms // 1000
    sec = total_sec % 60
    total_min = total_sec // 60
    minute = total_min % 60
    hour = total_min // 60
    return f"{hour:02d}:{minute:02d}:{sec:02d},{ms:03d}"


def wrap_subtitle_text(text: str, max_chars_per_line: int = 42, max_lines: int = 2) -> str:
    """Wrap text to subtitle display constraints."""
    lines = textwrap.wrap(text.strip(), width=max_chars_per_line)
    if len(lines) > max_lines:
        # Collapse excess into the second line
        lines = [lines[0], " ".join(lines[1:])]
    return "\n".join(lines)


def generate_srt_content(
    segments: list[TranslatedSegment],
    dual: bool = False,
    max_chars_per_line: int = 42,
) -> str:
    """Generate valid SubRip (.srt) text content from translated segments."""
    entries: list[str] = []
    cue_idx = 1

    # Ensure segments are sorted by start time
    sorted_segments = sorted(segments, key=lambda s: s.seg.start)

    for trans in sorted_segments:
        start_str = format_srt_timestamp(trans.seg.start)
        # Ensure minimum subtitle duration of 1.0s or until end
        end_time = max(trans.seg.end, trans.seg.start + 0.8)
        end_str = format_srt_timestamp(end_time)

        translated_wrapped = wrap_subtitle_text(trans.text, max_chars_per_line)
        if dual and trans.seg.text and trans.seg.text != trans.text:
            orig_wrapped = wrap_subtitle_text(trans.seg.text, max_chars_per_line, max_lines=1)
            cue_text = f"{orig_wrapped}\n{translated_wrapped}"
        else:
            cue_text = translated_wrapped

        entry = f"{cue_idx}\n{start_str} --> {end_str}\n{cue_text}\n"
        entries.append(entry)
        cue_idx += 1

    return "\n".join(entries)


def export_srt(
    segments: list[TranslatedSegment],
    output_path: Path,
    dual: bool = False,
) -> Path:
    """Write translated segments to an .srt file on disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = generate_srt_content(segments, dual=dual)
    output_path.write_text(content, encoding="utf-8")
    return output_path
