"""Full timeline audio rendering: ducked original audio track mixed with synthesized dub clips."""

from pathlib import Path

import numpy as np
import soundfile as sf

from voxstream.models import DubClip


def db_to_linear(db: float) -> float:
    """Convert decibel attenuation to linear amplitude factor."""
    return float(10.0 ** (db / 20.0))


def render_dub_track(
    clips: list[DubClip],
    total_duration: float,
    output_wav: Path,
    original_audio_wav: Path | None = None,
    sample_rate: int = 24000,
    duck_db: float = -14.0,
    duck_attack_ms: float = 120.0,
    duck_release_ms: float = 300.0,
) -> Path:
    """Render complete timeline WAV with ducked original audio and perfectly aligned dub clips."""
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    total_samples = int(total_duration * sample_rate)

    # 1. Prepare original audio buffer
    duck_factor = db_to_linear(duck_db)
    if original_audio_wav and original_audio_wav.exists():
        orig_data, orig_sr = sf.read(str(original_audio_wav))
        if orig_data.ndim > 1:
            orig_data = np.mean(orig_data, axis=1)
        # Resample if necessary
        if orig_sr != sample_rate:
            import shutil
            import subprocess

            temp_resample = output_wav.with_suffix(".orig_resample.wav")
            ffmpeg_bin = shutil.which("ffmpeg")
            if ffmpeg_bin:
                subprocess.run(
                    [
                        ffmpeg_bin,
                        "-y",
                        "-i",
                        str(original_audio_wav),
                        "-ar",
                        str(sample_rate),
                        "-ac",
                        "1",
                        str(temp_resample),
                    ],
                    capture_output=True,
                    check=False,
                )
                if temp_resample.exists():
                    orig_data, _ = sf.read(str(temp_resample))
                    temp_resample.unlink(missing_ok=True)

        orig_data = orig_data.astype(np.float32)
        if len(orig_data) < total_samples:
            padded = np.zeros(total_samples, dtype=np.float32)
            padded[: len(orig_data)] = orig_data
            orig_data = padded
        else:
            orig_data = orig_data[:total_samples]
    else:
        orig_data = np.zeros(total_samples, dtype=np.float32)

    # 2. Build ducking envelope array (1.0 = full original volume, duck_factor = ducked)
    envelope = np.ones(total_samples, dtype=np.float32)
    attack_samples = int((duck_attack_ms / 1000.0) * sample_rate)
    release_samples = int((duck_release_ms / 1000.0) * sample_rate)

    # 3. Sort clips and resolve any overlap
    sorted_clips = sorted(clips, key=lambda c: c.start)
    dub_track = np.zeros(total_samples, dtype=np.float32)

    for i, clip in enumerate(sorted_clips):
        start_idx = int(clip.start * sample_rate)
        if start_idx >= total_samples:
            continue

        if not clip.audio_path.exists():
            continue

        clip_data, _ = sf.read(str(clip.audio_path))
        if clip_data.ndim > 1:
            clip_data = np.mean(clip_data, axis=1)
        clip_data = clip_data.astype(np.float32)

        # Overlap resolution: ensure clip doesn't overlap next clip
        end_idx = start_idx + len(clip_data)
        if i + 1 < len(sorted_clips):
            next_start_idx = int(sorted_clips[i + 1].start * sample_rate)
            if end_idx > next_start_idx:
                # Trim clip trailing overflow with 30ms fade
                allowed_samples = max(0, next_start_idx - start_idx)
                clip_data = clip_data[:allowed_samples]
                fade_n = min(int(sample_rate * 0.03), len(clip_data))
                if fade_n > 0:
                    clip_data[-fade_n:] *= np.linspace(1.0, 0.0, fade_n, dtype=np.float32)
                end_idx = start_idx + len(clip_data)

        # Place clip in dub track
        slice_len = min(len(clip_data), total_samples - start_idx)
        dub_track[start_idx : start_idx + slice_len] += clip_data[:slice_len]

        # Apply ducking envelope to original audio
        duck_start = max(0, start_idx - attack_samples)
        duck_end = min(total_samples, start_idx + slice_len + release_samples)

        # Linear ramp down to duck_factor
        if attack_samples > 0 and start_idx > duck_start:
            ramp_down = np.linspace(1.0, duck_factor, start_idx - duck_start, dtype=np.float32)
            envelope[duck_start:start_idx] = np.minimum(envelope[duck_start:start_idx], ramp_down)

        # Sustained ducking while speech is active
        envelope[start_idx : start_idx + slice_len] = np.minimum(
            envelope[start_idx : start_idx + slice_len], duck_factor
        )

        # Linear ramp back up
        if release_samples > 0 and duck_end > (start_idx + slice_len):
            ramp_up = np.linspace(
                duck_factor, 1.0, duck_end - (start_idx + slice_len), dtype=np.float32
            )
            envelope[start_idx + slice_len : duck_end] = np.minimum(
                envelope[start_idx + slice_len : duck_end], ramp_up
            )

    # 4. Mix ducked original track and dub track
    mixed = (orig_data * envelope) + dub_track

    # Normalize to prevent digital clipping
    max_peak = np.max(np.abs(mixed))
    if max_peak > 0.98:
        mixed = mixed / max_peak * 0.95

    sf.write(str(output_wav), mixed, sample_rate, format="WAV", subtype="FLOAT")
    return output_wav
