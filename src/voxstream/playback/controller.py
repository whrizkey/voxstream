"""Playback controller coordinating player engine, lookahead scheduler, and subtitle cues."""

from pathlib import Path

from voxstream.config import get_settings
from voxstream.media.fingerprint import calculate_fingerprint
from voxstream.media.probe import probe_media
from voxstream.models import TranslatedSegment
from voxstream.pipeline.cache import CacheManager
from voxstream.pipeline.chunker import plan_chunks
from voxstream.pipeline.scheduler import LookaheadScheduler
from voxstream.playback.player import Player, VirtualPlayer
from voxstream.playback.subtitles import Cue, SubtitleStore
from voxstream.providers.base import SttProvider, TranslateProvider
from voxstream.providers.registry import (
    check_provider_usable,
    get_stt_provider,
    get_translate_provider,
)


class PlaybackController:
    """Coordinates video player, lookahead scheduler, and subtitle cues."""

    def __init__(
        self,
        media_path: Path,
        target_lang: str,
        *,
        source_lang: str | None = None,
        player: Player | None = None,
        stt_provider: SttProvider | None = None,
        translate_provider: TranslateProvider | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.media_path = media_path
        self.target_lang = target_lang
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

        # 4. Subtitle Store
        self.subtitles = SubtitleStore()

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
        self.scheduler.register_chunk_ready_callback(self._on_chunk_ready)
        self.scheduler.register_buffering_callback(self._on_buffering)
        self.player.register_seek_callback(self.scheduler.on_seek)

        self.is_buffering = False

    def _on_chunk_ready(self, chunk_idx: int, translations: list[TranslatedSegment]) -> None:
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

    def _on_buffering(self, buffering: bool) -> None:
        self.is_buffering = buffering
        if buffering and self.settings.pause_on_underrun:
            self.player.pause()
        elif not buffering and self.settings.pause_on_underrun:
            self.player.play()

    async def step(self) -> None:
        """Advance scheduler lookahead cycle."""
        await self.scheduler.step()

    def get_active_subtitle(self) -> Cue | None:
        """Get the subtitle cue corresponding to the current player time position."""
        current_time = self.player.get_time_pos()
        return self.subtitles.get_active_cue(current_time)

    def seek(self, target_pos: float) -> None:
        self.player.seek(target_pos)
