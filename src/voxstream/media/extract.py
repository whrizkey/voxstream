"""Audio extraction utilities using FFmpeg."""

import shutil
import subprocess
from pathlib import Path

from voxstream.errors import MediaError
from voxstream.media.probe import probe_media


def extract_audio_chunk(
    input_media: str | Path,
    output_wav: Path,
    *,
    start_seconds: float,
    duration_seconds: float,
    sample_rate: int = 16000,
    channels: int = 1,
    tolerance_ms: float = 80.0,
) -> Path:
    """Extract an audio slice to 16-bit PCM WAV using input-side fast seeking."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        # Fallback for local audio files using soundfile if ffmpeg is absent
        try:
            import numpy as np
            import soundfile as sf

            data, sr = sf.read(str(input_media))
            start_frame = int(max(0.0, start_seconds) * sr)
            end_frame = int((start_seconds + duration_seconds) * sr)
            slice_data = data[start_frame:end_frame]
            if slice_data.ndim > 1 and channels == 1:
                slice_data = np.mean(slice_data, axis=1)
            output_wav.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output_wav), slice_data, sr, subtype="PCM_16")
            return output_wav
        except Exception:
            raise MediaError(
                "ffmpeg binary not found on PATH. Install ffmpeg to extract audio."
            ) from None

    output_wav.parent.mkdir(parents=True, exist_ok=True)
    temp_wav = output_wav.with_suffix(".tmp.wav")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-ss",
        f"{max(0.0, start_seconds):.3f}",
        "-t",
        f"{duration_seconds:.3f}",
        "-i",
        str(input_media),
        "-vn",
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        str(temp_wav),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    except subprocess.TimeoutExpired as exc:
        if temp_wav.exists():
            temp_wav.unlink(missing_ok=True)
        raise MediaError(f"Audio extraction timed out for {input_media}") from exc

    if proc.returncode != 0:
        if temp_wav.exists():
            temp_wav.unlink(missing_ok=True)
        raise MediaError(f"ffmpeg extraction failed: {proc.stderr.strip()}")

    # Verify extracted duration
    try:
        probe = probe_media(temp_wav)
        if probe.duration <= 0.0:
            raise MediaError(f"Extracted audio file is empty: {temp_wav}")
        temp_wav.replace(output_wav)
    except Exception as exc:
        if temp_wav.exists():
            temp_wav.unlink(missing_ok=True)
        raise MediaError(f"Failed to verify extracted audio: {exc}") from exc

    return output_wav
