"""Media probing using ffprobe."""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from voxstream.errors import MediaError


@dataclass(frozen=True)
class MediaProbeResult:
    path_or_url: str
    duration: float
    has_audio: bool
    has_video: bool
    fps: float | None = None
    audio_sample_rate: int | None = None
    audio_channels: int | None = None


def probe_media(path_or_url: str | Path) -> MediaProbeResult:
    """Probe media file or stream URL using ffprobe."""
    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        # Fallback to soundfile for audio files if ffprobe binary is absent
        try:
            import soundfile as sf

            info = sf.info(str(path_or_url))
            return MediaProbeResult(
                path_or_url=str(path_or_url),
                duration=float(info.duration),
                has_audio=True,
                has_video=False,
                audio_sample_rate=int(info.samplerate),
                audio_channels=int(info.channels),
            )
        except Exception:
            raise MediaError(
                "ffprobe binary not found on system PATH. Install ffmpeg to probe media."
            ) from None

    target_str = str(path_or_url)
    if not target_str.startswith(("http://", "https://")):
        path_obj = Path(path_or_url)
        if not path_obj.exists():
            raise MediaError(f"Media file does not exist: {target_str}")

    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,r_frame_rate,sample_rate,channels",
        "-of",
        "json",
        target_str,
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
    except subprocess.TimeoutExpired as exc:
        raise MediaError(f"ffprobe timed out while probing {target_str}") from exc
    except Exception as exc:
        raise MediaError(f"Error running ffprobe on {target_str}: {exc}") from exc

    if proc.returncode != 0:
        raise MediaError(f"ffprobe failed for {target_str}: {proc.stderr.strip()}")

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise MediaError(f"Invalid JSON output from ffprobe: {proc.stdout}") from exc

    format_info = data.get("format", {})
    duration_str = format_info.get("duration")
    duration = float(duration_str) if duration_str is not None else 0.0

    streams = data.get("streams", [])
    has_audio = False
    has_video = False
    fps: float | None = None
    sample_rate: int | None = None
    channels: int | None = None

    for stream in streams:
        codec_type = stream.get("codec_type")
        if codec_type == "audio":
            has_audio = True
            if stream.get("sample_rate"):
                try:
                    sample_rate = int(stream["sample_rate"])
                except (ValueError, TypeError):
                    pass
            if stream.get("channels"):
                try:
                    channels = int(stream["channels"])
                except (ValueError, TypeError):
                    pass
        elif codec_type == "video":
            has_video = True
            r_frame_rate = stream.get("r_frame_rate")
            if r_frame_rate and "/" in r_frame_rate:
                try:
                    num, den = r_frame_rate.split("/")
                    if float(den) > 0:
                        fps = float(num) / float(den)
                except (ValueError, ZeroDivisionError):
                    pass

    return MediaProbeResult(
        path_or_url=target_str,
        duration=duration,
        has_audio=has_audio,
        has_video=has_video,
        fps=fps,
        audio_sample_rate=sample_rate,
        audio_channels=channels,
    )
