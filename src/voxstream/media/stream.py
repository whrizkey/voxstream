"""Online video and audio streaming resolution via yt-dlp."""

import asyncio
import json
import shutil
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from voxstream.errors import ExternalToolError, MediaError


@dataclass(frozen=True)
class StreamInfo:
    """Resolved online media stream endpoints."""

    url: str
    title: str
    duration: float
    video_url: str
    audio_url: str


def is_stream_url(target: str) -> bool:
    """Check if target string is an HTTP/HTTPS/RTMP streaming URL."""
    try:
        parsed = urlparse(target)
        return parsed.scheme.lower() in ("http", "https", "rtmp", "rtsp", "mms")
    except Exception:
        return False


async def resolve_stream_info(url: str) -> StreamInfo:
    """Resolve direct media streaming URLs using yt-dlp."""
    if not is_stream_url(url):
        raise MediaError(f"Target '{url}' is not a valid streaming URL.")

    ytdlp_bin = shutil.which("yt-dlp")
    if not ytdlp_bin:
        raise ExternalToolError(
            "yt-dlp CLI not found on PATH. Install with `pip install yt-dlp` to stream online videos."
        )

    cmd = [
        ytdlp_bin,
        "--dump-single-json",
        "--no-warnings",
        "--prefer-free-formats",
        url,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise ExternalToolError(
            f"yt-dlp failed to resolve '{url}': {stderr.decode(errors='replace').strip()}"
        )

    try:
        data: dict[str, Any] = json.loads(stdout.decode(errors="replace"))
    except json.JSONDecodeError as exc:
        raise ExternalToolError(f"Failed to parse yt-dlp JSON output: {exc}") from exc

    title = str(data.get("title", "Online Stream"))
    duration = float(data.get("duration", 0.0) or 0.0)

    # Pick direct stream URL or audio URL
    direct_url = str(data.get("url", url))
    audio_url = direct_url

    # Inspect formats if available for separate bestaudio stream
    formats = data.get("formats", [])
    if isinstance(formats, list):
        audio_formats = [
            f
            for f in formats
            if isinstance(f, dict)
            and f.get("vcodec") == "none"
            and f.get("acodec") != "none"
            and f.get("url")
        ]
        if audio_formats:
            best_audio = max(audio_formats, key=lambda f: float(f.get("abr", 0) or 0))
            audio_url = str(best_audio["url"])

    return StreamInfo(
        url=url,
        title=title,
        duration=duration,
        video_url=direct_url,
        audio_url=audio_url,
    )
