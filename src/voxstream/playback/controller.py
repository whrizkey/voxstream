"""Playback controller coordinating player engine, lookahead scheduler, subtitles, and dub mixer."""

from pathlib import Path
from typing import Any

from voxstream.config import get_settings
from voxstream.media.fingerprint import calculate_fingerprint
from voxstream.media.probe import probe_media
from voxstream.models import DubClip, TranslatedSegment
from voxstream.pipeline.cache import CacheManager
from voxstream.pipeline.chunker import plan_chunks
from voxstream.pipeline.scheduler import LookaheadScheduler
from voxstream.playback.mixer import DubMixer
from voxstream.playback.player import Player, VirtualPlayer
from voxstream.playback.subtitles import Cue, SubtitleStore
from voxstream.providers.base import SttProvider, TranslateProvider, TtsProvider
from voxstream.providers.registry import (
    check_provider_usable,
    get_stt_provider,
    get_translate_provider,
    get_tts_provider,
)


class PlaybackController:
    """Coordinates video player, lookahead scheduler, subtitle store, and dub mixer."""

    def __init__(
        self,
        media_path: Path,
        target_lang: str,
        *,
        mode: str = "subs",
        source_lang: str | None = None,
        player: Player | None = None,
        stt_provider: SttProvider | None = None,
        translate_provider: TranslateProvider | None = None,
        tts_provider: TtsProvider | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.media_path = media_path
        self.target_lang = target_lang
        self.mode = mode
        self.source_lang = source_lang
        self.settings = get_settings()

        # 1. Probe media
        self.probe = probe_media(media_path)
        self.media_id = calculate_fingerprint(media_path, self.probe.duration)

        # 2. Player
        self.player = player or VirtualPlayer(duration=self.probe.duration)
        self.player.load(media_path)

        # 3. Cache & Providers
        self.cache = CacheManager(cache_dir or self.settings.get_cache_path())
        self.cache.record_media(self.media_id, str(media_path), self.probe.duration)

        if stt_provider is None:
            status = check_provider_usable("stt", self.settings.stt_provider)
            self.stt_provider = get_stt_provider(
                self.settings.stt_provider if status.is_usable else "fake"
            )
        else:
            self.stt_provider = stt_provider

        if translate_provider is None:
            t_status = check_provider_usable("translate", self.settings.translate_provider)
            self.translate_provider = get_translate_provider(
                self.settings.translate_provider if t_status.is_usable else "fake"
            )
        else:
            self.translate_provider = translate_provider

        self.tts_provider: TtsProvider | None = None
        if tts_provider is None and self.mode in ("dub", "both"):
            tts_status = check_provider_usable("tts", self.settings.tts_provider)
            self.tts_provider = get_tts_provider(
                self.settings.tts_provider if tts_status.is_usable else "fake"
            )
        else:
            self.tts_provider = tts_provider

        # 4. Subtitle Store & Dub Mixer
        self.subtitles = SubtitleStore()
        self.mixer = DubMixer(
            sample_rate=24000,
            duck_db=self.settings.duck_db,
        )

        # 5. Chunks & Scheduler
        self.chunks = plan_chunks(
            total_duration=self.probe.duration,
            chunk_seconds=self.settings.chunk_seconds,
            overlap_seconds=self.settings.chunk_overlap_seconds,
        )

        self.scheduler = LookaheadScheduler(
            playhead_fn=self.player.get_time_pos,
            chunks=self.chunks,
            media_id=self.media_id,
            media_path=self.media_path,
            cache=self.cache,
            stt_provider=self.stt_provider,
            translate_provider=self.translate_provider,
            target_lang=self.target_lang,
            source_lang=self.source_lang,
            lookahead_seconds=self.settings.lookahead_seconds,
            initial_buffer_seconds=self.settings.initial_buffer_seconds,
            pause_on_underrun=self.settings.pause_on_underrun,
        )

        # Wire callbacks
        self._background_tasks: set[Any] = set()
        self.scheduler.register_chunk_ready_callback(self._on_chunk_ready)
        self.scheduler.register_buffering_callback(self._on_buffering)
        self.player.register_seek_callback(self._on_player_seek)
        self.player.register_time_pos_callback(self._on_time_pos_update)

        self.is_buffering = False

    def _on_time_pos_update(self, current_pos: float) -> None:
        self.mixer.update_anchor(current_pos)

    def _on_player_seek(self, target_pos: float) -> None:
        self.scheduler.on_seek(target_pos)
        self.mixer.seek(target_pos)

    def _on_chunk_ready(self, chunk_idx: int, translations: list[TranslatedSegment]) -> None:
        # 1. Update Subtitles
        cues = [
            Cue(
                start=t.seg.start,
                end=t.seg.end,
                text=t.text,
                original_text=t.seg.text,
            )
            for t in translations
        ]
        self.subtitles.add_cues(cues)

        # 2. If dubbing mode, schedule synthesis in background
        if self.mode in ("dub", "both") and self.tts_provider is not None:
            import asyncio

            async def _synthesize_clips() -> None:
                from voxstream.pipeline.synthesize import synthesize_and_fit_segment

                tts_dir = self.cache.get_media_dir(self.media_id) / "tts"
                clips: list[DubClip] = []
                for idx, trans_seg in enumerate(translations):
                    next_start = (
                        translations[idx + 1].seg.start if idx + 1 < len(translations) else None
                    )
                    if self.tts_provider is None:
                        continue
                    clip = await synthesize_and_fit_segment(
                        trans_seg,
                        next_start,
                        self.tts_provider,
                        self.translate_provider,
                        tts_dir,
                        max_speedup=self.settings.max_speedup,
                        voice=self.settings.tts_voice,
                    )
                    clips.append(clip)
                self.mixer.add_clips(clips)

            # Schedule or run synchronously
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(_synthesize_clips())
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
            except RuntimeError:
                asyncio.run(_synthesize_clips())

    def _on_buffering(self, buffering: bool) -> None:
        self.is_buffering = buffering
        if buffering and self.settings.pause_on_underrun:
            self.player.pause()
            self.mixer.pause()
        elif not buffering and self.settings.pause_on_underrun:
            self.player.play()
            self.mixer.resume()

    async def step(self) -> None:
        """Advance scheduler lookahead cycle."""
        await self.scheduler.step()

    def get_active_subtitle(self) -> Cue | None:
        """Get the subtitle cue corresponding to the current player time position."""
        current_time = self.player.get_time_pos()
        return self.subtitles.get_active_cue(current_time)

    def seek(self, target_pos: float) -> None:
        self.player.seek(target_pos)

    def play(self) -> None:
        self.player.play()
        self.mixer.resume()

    def pause(self) -> None:
        self.player.pause()
        self.mixer.pause()
