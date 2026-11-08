"""Batch offline processing pipeline for subtitles and dubbing."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from voxstream.config import get_settings
from voxstream.export.srt import export_srt
from voxstream.media.extract import extract_audio_chunk
from voxstream.media.fingerprint import calculate_fingerprint
from voxstream.media.probe import probe_media
from voxstream.models import TranslatedSegment
from voxstream.pipeline.cache import (
    CacheManager,
    make_stt_key,
    make_translate_key,
)
from voxstream.pipeline.chunker import plan_chunks
from voxstream.pipeline.transcribe import transcribe_chunk
from voxstream.pipeline.translate import translate_segments
from voxstream.providers.base import SttProvider, TranslateProvider
from voxstream.providers.registry import (
    get_stt_provider,
    get_translate_provider,
)


async def process_media_offline(
    input_path: Path,
    target_lang: str,
    output_dir: Path,
    *,
    mode: str = "subs",
    source_lang: str | None = None,
    dual_subtitles: bool = False,
    stt_provider: SttProvider | None = None,
    translate_provider: TranslateProvider | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    """Execute complete offline batch processing for subtitles and/or dubbing."""
    settings = get_settings()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Probe & fingerprint
    probe = probe_media(input_path)
    media_id = calculate_fingerprint(input_path, probe.duration)

    cache = CacheManager(settings.get_cache_path())
    cache.record_media(media_id, str(input_path), probe.duration)
    media_cache_dir = cache.get_media_dir(media_id)
    audio_dir = media_cache_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # 2. Plan chunks
    chunks = plan_chunks(
        total_duration=probe.duration,
        chunk_seconds=settings.chunk_seconds,
        overlap_seconds=settings.chunk_overlap_seconds,
    )

    if stt_provider is None:
        from voxstream.providers.registry import check_provider_usable

        status = check_provider_usable("stt", settings.stt_provider)
        stt_provider = get_stt_provider(settings.stt_provider if status.is_usable else "fake")

    if translate_provider is None:
        from voxstream.providers.registry import check_provider_usable

        t_status = check_provider_usable("translate", settings.translate_provider)
        translate_provider = get_translate_provider(
            settings.translate_provider if t_status.is_usable else "fake"
        )

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
    cache_hits = 0
    context_lines: list[str] = []

    for chunk in chunks:
        if progress_callback:
            progress_callback(chunk.index, len(chunks), f"Chunk {chunk.index + 1}/{len(chunks)}")

        # Check transcript cache
        cached_segments = cache.get_transcript(media_id, chunk.index, stt_key)
        if cached_segments is not None:
            segments = cached_segments
            cache_hits += 1
        else:
            # Extract audio and transcribe
            chunk_wav = audio_dir / f"chunk_{chunk.index}.wav"
            extract_audio_chunk(
                input_path,
                chunk_wav,
                start_seconds=chunk.extraction_start,
                duration_seconds=chunk.extraction_duration,
            )
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
        # Update context lines
        context_lines.extend([t.text for t in translations[-3:]])

    # 3. Export SRT
    stem = input_path.stem
    srt_path = output_dir / f"{stem}.{target_lang}.srt"
    export_srt(all_translations, srt_path, dual=dual_subtitles)

    return {
        "media_id": media_id,
        "duration": probe.duration,
        "total_chunks": len(chunks),
        "cache_hits": cache_hits,
        "total_segments": len(all_translations),
        "srt_path": srt_path,
    }
