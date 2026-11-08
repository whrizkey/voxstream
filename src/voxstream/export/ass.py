"""Advanced SubStation Alpha (.ass) subtitle exporter with style presets and dual-subtitle support."""

from pathlib import Path
from typing import ClassVar

from voxstream.models import TranslatedSegment


def _format_ass_timestamp(seconds: float) -> str:
    """Format seconds into ASS timestamp: H:MM:SS.cc (centiseconds)."""
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = round((seconds - int(seconds)) * 100)
    if centis == 100:
        secs += 1
        centis = 0
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


class AssStyles:
    """Preset styles for ASS subtitles.

    Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour,
    BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle,
    BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    """

    PRESETS: ClassVar[dict[str, str]] = {
        "default": (
            "Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
            "-1,0,0,0,100,100,0,0,1,2,1,2,20,20,20,1"
        ),
        "anime": (
            "Style: Anime,Trebuchet MS,22,&H0000FFFF,&H000000FF,&H00000000,&H90000000,"
            "-1,0,0,0,100,100,0,0,1,2.5,1.5,2,20,20,24,1"
        ),
        "cinematic": (
            "Style: Cinematic,Calibri,21,&H00E0E0E0,&H000000FF,&H00101010,&HB0000000,"
            "0,0,0,0,100,100,0.5,0,1,1.5,0.8,2,30,30,30,1"
        ),
        "dual_top": (
            "Style: DualTop,Arial,16,&H00C0C0C0,&H000000FF,&H00000000,&H80000000,"
            "0,1,0,0,100,100,0,0,1,1.5,1,8,20,20,20,1"
        ),
        "dual_bottom": (
            "Style: DualBottom,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
            "-1,0,0,0,100,100,0,0,1,2,1,2,20,20,20,1"
        ),
    }


def export_ass(
    segments: list[TranslatedSegment],
    output_path: Path,
    *,
    style: str = "default",
    dual: bool = False,
    title: str = "VoxStream Subtitles",
) -> Path:
    """Export translated segments to ASS subtitle file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        "[Script Info]",
        f"Title: {title}",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: None",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    ]

    if dual:
        header.append(AssStyles.PRESETS["dual_top"])
        header.append(AssStyles.PRESETS["dual_bottom"])
    else:
        preset_line = AssStyles.PRESETS.get(style, AssStyles.PRESETS["default"])
        header.append(preset_line)

    header.extend(
        [
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )

    lines: list[str] = list(header)
    for seg in sorted(segments, key=lambda s: s.seg.start):
        start_ts = _format_ass_timestamp(seg.seg.start)
        end_ts = _format_ass_timestamp(seg.seg.end)

        if dual:
            # Render original on top, translation on bottom
            orig_text = seg.seg.text.replace("\n", "\\N")
            trans_text = seg.text.replace("\n", "\\N")
            lines.append(f"Dialogue: 0,{start_ts},{end_ts},DualTop,,0,0,0,,{orig_text}")
            lines.append(f"Dialogue: 0,{start_ts},{end_ts},DualBottom,,0,0,0,,{trans_text}")
        else:
            style_name = (
                "Anime"
                if style == "anime"
                else ("Cinematic" if style == "cinematic" else "Default")
            )
            clean_text = seg.text.replace("\n", "\\N")
            lines.append(f"Dialogue: 0,{start_ts},{end_ts},{style_name},,0,0,0,,{clean_text}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path
