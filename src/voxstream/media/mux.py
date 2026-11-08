"""Mux video, original audio, dubbed track, and subtitles using FFmpeg."""

import shutil
import subprocess
from pathlib import Path

from voxstream.errors import MediaError


def mux_media(
    video_path: Path,
    output_path: Path,
    *,
    dub_audio_path: Path | None = None,
    subtitle_path: Path | None = None,
    target_lang: str | None = None,
) -> Path:
    """Mux original video with extra dubbed audio track and subtitle track."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise MediaError("ffmpeg binary not found on system PATH. Install ffmpeg to mux media.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.resolve() == video_path.resolve():
        raise MediaError("Output path cannot overwrite input video file directly.")

    cmd = [ffmpeg_bin, "-y", "-i", str(video_path)]

    input_count = 1
    dub_idx: int | None = None
    sub_idx: int | None = None

    if dub_audio_path and dub_audio_path.exists():
        cmd.extend(["-i", str(dub_audio_path)])
        dub_idx = input_count
        input_count += 1

    if subtitle_path and subtitle_path.exists():
        cmd.extend(["-i", str(subtitle_path)])
        sub_idx = input_count
        input_count += 1

    # Map video and original audio from input 0 (optional if video absent)
    cmd.extend(["-map", "0:v:0?", "-map", "0:a?"])

    # Map dub audio track if present
    if dub_idx is not None:
        cmd.extend(["-map", f"{dub_idx}:a:0"])

    # Map subtitles if present
    if sub_idx is not None:
        cmd.extend(["-map", f"{sub_idx}:s:0"])

    # Copy video without re-encoding
    cmd.extend(["-c:v", "copy"])

    # Codecs for audio and subtitles depending on container
    is_mp4 = output_path.suffix.lower() == ".mp4"
    cmd.extend(["-c:a", "aac"])
    if sub_idx is not None:
        cmd.extend(["-c:s", "mov_text" if is_mp4 else "srt"])

    # Metadata tagging
    if target_lang:
        lang_code = target_lang.lower().split("-")[0]
        if dub_idx is not None:
            cmd.extend(
                [
                    "-metadata:s:a:1",
                    f"language={lang_code}",
                    "-metadata:s:a:1",
                    f"title=Dubbed ({lang_code})",
                ]
            )
        if sub_idx is not None:
            cmd.extend(
                [
                    "-metadata:s:s:0",
                    f"language={lang_code}",
                    "-metadata:s:s:0",
                    f"title=Subtitles ({lang_code})",
                ]
            )

    cmd.append(str(output_path))

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise MediaError(f"ffmpeg muxing failed: {proc.stderr.strip()}")

    return output_path
