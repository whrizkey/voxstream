"""Stage 3: Text-to-Speech synthesis and time-fitting execution."""

import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from voxstream.errors import MediaError
from voxstream.models import DubClip, TranslatedSegment
from voxstream.pipeline.fit import fit_clip
from voxstream.providers.base import TranslateItem, TranslateProvider, TtsProvider


def time_stretch_audio(
    input_wav: Path,
    output_wav: Path,
    speed_factor: float,
    target_duration: float | None = None,
) -> Path:
    """Time-stretch audio using ffmpeg atempo filter while preserving pitch."""
    if abs(speed_factor - 1.0) < 0.02:
        shutil.copy2(input_wav, output_wav)
        return output_wav

    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise MediaError("ffmpeg binary not found for audio time stretching.")

    output_wav.parent.mkdir(parents=True, exist_ok=True)
    temp_wav = output_wav.with_suffix(".stretch_tmp.wav")

    # ffmpeg atempo accepts factors between 0.5 and 2.0
    clamped_speed = max(0.5, min(2.0, speed_factor))
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(input_wav),
        "-filter:a",
        f"atempo={clamped_speed:.3f}",
        "-vn",
        str(temp_wav),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        if proc.returncode != 0:
            shutil.copy2(input_wav, output_wav)
            return output_wav
        temp_wav.replace(output_wav)
    finally:
        if temp_wav.exists():
            temp_wav.unlink(missing_ok=True)

    return output_wav


def apply_fade_out_and_truncate(wav_path: Path, max_duration: float, fade_ms: float = 60.0) -> None:
    """Truncate audio array to max_duration and apply a smooth linear fade-out."""
    data, sr = sf.read(str(wav_path))
    max_samples = int(max_duration * sr)
    if len(data) <= max_samples:
        return

    data = data[:max_samples]
    fade_samples = min(int((fade_ms / 1000.0) * sr), len(data))
    if fade_samples > 0:
        fade_curve = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
        data[-fade_samples:] *= fade_curve

    sf.write(str(wav_path), data, sr, format="WAV", subtype="FLOAT")


async def synthesize_and_fit_segment(
    trans_seg: TranslatedSegment,
    next_seg_start: float | None,
    tts_provider: TtsProvider,
    translate_provider: TranslateProvider | None,
    output_dir: Path,
    *,
    max_speedup: float = 1.25,
    voice: str | None = None,
) -> DubClip:
    """Synthesize speech, apply time-fitting, and retranslate on overflow if required."""
    output_dir.mkdir(parents=True, exist_ok=True)
    seg = trans_seg.seg

    # 1. First synthesis attempt
    raw_wav = await tts_provider.synthesize(trans_seg.text, lang=trans_seg.target_lang, voice=voice)
    data, sr = sf.read(str(raw_wav))
    clip_dur = len(data) / sr

    decision = fit_clip(
        seg.start,
        seg.end,
        next_seg_start,
        clip_dur,
        max_speedup=max_speedup,
        allow_retranslation=bool(translate_provider is not None),
    )

    final_text = trans_seg.text
    final_wav = raw_wav

    # 2. Retranslate once if clip exceeds room
    if decision.needs_retranslation and translate_provider is not None:
        slot = seg.end - seg.start
        shorter_max_chars = max(10, int(len(trans_seg.text) * decision.scale_factor))
        retrans_items = [
            TranslateItem(
                id=seg.seg_id,
                text=seg.text,
                max_chars=shorter_max_chars,
                duration=slot,
            )
        ]
        try:
            results = await translate_provider.translate(
                retrans_items,
                source_lang=seg.language,
                target_lang=trans_seg.target_lang,
                context=[],
            )
            if results and results[0].text:
                final_text = results[0].text
                if final_wav.exists():
                    final_wav.unlink(missing_ok=True)
                final_wav = await tts_provider.synthesize(
                    final_text, lang=trans_seg.target_lang, voice=voice
                )
                data, sr = sf.read(str(final_wav))
                clip_dur = len(data) / sr
        except Exception:
            pass  # Fall back to original synthesis with stretching

        decision = fit_clip(
            seg.start,
            seg.end,
            next_seg_start,
            clip_dur,
            max_speedup=max_speedup,
            allow_retranslation=False,
        )

    # 3. Apply time stretching / truncation if necessary
    processed_clip_path = output_dir / f"{seg.seg_id}.wav"
    if decision.speed_factor > 1.01:
        time_stretch_audio(final_wav, processed_clip_path, decision.speed_factor)
        if final_wav.exists():
            final_wav.unlink(missing_ok=True)
    else:
        shutil.move(final_wav, processed_clip_path)

    if "truncated" in decision.flags:
        apply_fade_out_and_truncate(processed_clip_path, decision.effective_duration)

    data, sr = sf.read(str(processed_clip_path))
    actual_duration = len(data) / sr

    return DubClip(
        seg_id=seg.seg_id,
        start=seg.start,
        audio_path=processed_clip_path,
        duration=actual_duration,
        speed_factor=decision.speed_factor,
        overflow=decision.overflow,
        flags=decision.flags,
    )
