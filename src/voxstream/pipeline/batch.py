"""Batch offline processing pipeline for subtitles and dubbing."""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from voxstream.config import get_settings
from voxstream.errors import ConfigurationError
from voxstream.export.dubtrack import render_dub_track
from voxstream.export.srt import export_srt
from voxstream.media.extract import extract_audio_chunk
from voxstream.media.fingerprint import calculate_fingerprint
from voxstream.media.mux import mux_media
from voxstream.media.probe import probe_media
from voxstream.models import DubClip, TranslatedSegment
from voxstream.pipeline.cache import (
    CacheManager,
    make_stt_key,
    make_translate_key,
)
from voxstream.pipeline.chunker import create_silence_finder, plan_chunks
from voxstream.pipeline.synthesize import synthesize_and_fit_segment
from voxstream.pipeline.transcribe import transcribe_chunk
from voxstream.pipeline.translate import translate_segments
from voxstream.providers.accounting import UsageTracker
from voxstream.providers.base import SttProvider, TranslateProvider, TtsProvider
from voxstream.providers.registry import (
    check_provider_usable,
    get_stt_provider,
    get_translate_provider,
    get_tts_provider,
)


async def process_media_offline(
    input_path: Path,
    target_lang: str,
    output_dir: Path,
    *,
    mode: str = "subs",
    source_lang: str | None = None,
    dual_subtitles: bool = False,
    mux: bool = False,
    stt_provider: SttProvider | None = None,
    translate_provider: TranslateProvider | None = None,
    tts_provider: TtsProvider | None = None,
    cache_dir: Path | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    """Execute complete offline batch processing for subtitles and/or dubbing."""
    settings = get_settings()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Probe & fingerprint
    probe = probe_media(input_path)
    media_id = calculate_fingerprint(input_path, probe.duration)

    effective_cache_dir = cache_dir or settings.get_cache_path()
    cache = CacheManager(effective_cache_dir)
    cache.record_media(media_id, str(input_path), probe.duration)
    media_cache_dir = cache.get_media_dir(media_id)
    audio_dir = media_cache_dir / "audio"
    tts_dir = media_cache_dir / "tts"
    audio_dir.mkdir(parents=True, exist_ok=True)
    tts_dir.mkdir(parents=True, exist_ok=True)

    # 2. Plan chunks with silence snapping
    silence_finder = create_silence_finder(input_path)
    chunks = plan_chunks(
        total_duration=probe.duration,
        chunk_seconds=settings.chunk_seconds,
        overlap_seconds=settings.chunk_overlap_seconds,
        silence_finder=silence_finder,
    )

    if stt_provider is None:
        status = check_provider_usable("stt", settings.stt_provider)
        if not status.is_usable and settings.stt_provider != "fake":
            raise ConfigurationError(
                f"STT provider '{settings.stt_provider}' is not usable: {status.reason}"
            )
        stt_provider = get_stt_provider(settings.stt_provider)

    if translate_provider is None:
        t_status = check_provider_usable("translate", settings.translate_provider)
        if not t_status.is_usable and settings.translate_provider != "fake":
            raise ConfigurationError(
                f"Translation provider '{settings.translate_provider}' is not usable: {t_status.reason}"
            )
        translate_provider = get_translate_provider(settings.translate_provider)

    if tts_provider is None and mode in ("dub", "both"):
        tts_status = check_provider_usable("tts", settings.tts_provider)
        if not tts_status.is_usable and settings.tts_provider != "fake":
            raise ConfigurationError(
                f"TTS provider '{settings.tts_provider}' is not usable: {tts_status.reason}"
            )
        tts_provider = get_tts_provider(settings.tts_provider)

    # Initialize usage and budget tracker
    tracker = UsageTracker(max_cost_usd=settings.max_cost_usd)

    chunk_params = f"{settings.chunk_seconds}:{settings.chunk_overlap_seconds}"
    stt_key = make_stt_key(stt_provider.name, settings.stt_model, source_lang, chunk_params)
    translate_key = make_translate_key(
        translate_provider.name,
        settings.translate_model,
        target_lang,
        prompt_version="v1",
        max_chars_mode=(mode in ("dub", "both")),
    )

    all_translations: list[TranslatedSegment] = []
    all_clips: list[DubClip] = []
    cache_hits = 0
    context_lines: list[str] = []

    # Extract original full audio non-blockingly if dubbing
    original_audio_wav: Path | None = None
    if mode in ("dub", "both") and probe.has_audio:
        original_audio_wav = audio_dir / "full_original.wav"
        if not original_audio_wav.exists():
            await asyncio.to_thread(
                extract_audio_chunk,
                input_path,
                original_audio_wav,
                start_seconds=0.0,
                duration_seconds=probe.duration,
            )

    for chunk in chunks:
        if progress_callback:
            progress_callback(chunk.index, len(chunks), f"Chunk {chunk.index + 1}/{len(chunks)}")

        # Check transcript cache
        cached_segments = cache.get_transcript(media_id, chunk.index, stt_key)
        if cached_segments is not None:
            segments = cached_segments
            cache_hits += 1
        else:
            chunk_wav = audio_dir / f"chunk_{chunk.index}.wav"
            await asyncio.to_thread(
                extract_audio_chunk,
                input_path,
                chunk_wav,
                start_seconds=chunk.extraction_start,
                duration_seconds=chunk.extraction_duration,
            )
            tracker.record_stt(stt_provider.name, chunk.extraction_duration)
            segments = await transcribe_chunk(
                stt_provider,
                chunk_wav,
                chunk,
                media_id,
                language=source_lang,
            )
            cache.set_transcript(media_id, chunk.index, stt_key, segments)

        # Check translation cache
        cached_translations = cache.get_translation(
            media_id, chunk.index, translate_key, target_lang
        )
        if cached_translations is not None:
            translations = cached_translations
        else:
            char_count = sum(len(s.text) for s in segments)
            tracker.record_translation(translate_provider.name, char_count)
            translations = await translate_segments(
                translate_provider,
                segments,
                target_lang=target_lang,
                source_lang=source_lang,
                context=context_lines,
                for_dubbing=(mode in ("dub", "both")),
            )
            cache.set_translation(media_id, chunk.index, translate_key, target_lang, translations)

        all_translations.extend(translations)
        context_lines.extend([t.text for t in translations[-3:]])

    # 3. Stage 3: Synthesis and Time Fitting (for dubbing)
    truncated_count = 0
    stretched_count = 0
    if mode in ("dub", "both") and tts_provider is not None:
        for idx, trans_seg in enumerate(all_translations):
            next_start = (
                all_translations[idx + 1].seg.start if idx + 1 < len(all_translations) else None
            )
            tracker.record_tts(tts_provider.name, len(trans_seg.text))
            clip = await synthesize_and_fit_segment(
                trans_seg,
                next_start,
                tts_provider,
                translate_provider,
                tts_dir,
                max_speedup=settings.max_speedup,
                voice=settings.tts_voice,
            )
            all_clips.append(clip)
            if "truncated" in clip.flags:
                truncated_count += 1
            if "stretched" in clip.flags:
                stretched_count += 1

    stem = input_path.stem
    srt_path = output_dir / f"{stem}.{target_lang}.srt"
    export_srt(all_translations, srt_path, dual=dual_subtitles)

    dub_wav_path: Path | None = None
    if mode in ("dub", "both") and all_clips:
        dub_wav_path = output_dir / f"{stem}.{target_lang}.dub.wav"
        render_dub_track(
            clips=all_clips,
            total_duration=probe.duration,
            output_wav=dub_wav_path,
            original_audio_wav=original_audio_wav,
            duck_db=settings.duck_db,
        )

    muxed_path: Path | None = None
    if mux:
        ext = ".mp4" if probe.has_video else ".mkv"
        muxed_path = output_dir / f"{stem}.{target_lang}.muxed{ext}"
        mux_media(
            video_path=input_path,
            output_path=muxed_path,
            dub_audio_path=dub_wav_path,
            subtitle_path=srt_path,
            target_lang=target_lang,
        )

    return {
        "media_id": media_id,
        "duration": probe.duration,
        "total_chunks": len(chunks),
        "cache_hits": cache_hits,
        "total_segments": len(all_translations),
        "total_clips": len(all_clips),
        "stretched_clips": stretched_count,
        "truncated_clips": truncated_count,
        "srt_path": srt_path,
        "dub_wav_path": dub_wav_path,
        "muxed_path": muxed_path,
        "cost_usd": tracker.estimate_cost_usd(),
        "usage_tracker": tracker,
    }
