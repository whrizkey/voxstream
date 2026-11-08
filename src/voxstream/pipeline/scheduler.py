"""Look-ahead pipeline orchestrator with generation tracking and underrun handling."""

from collections.abc import Callable
from pathlib import Path

from voxstream.models import ChunkSpec, ChunkState, TranslatedSegment
from voxstream.pipeline.cache import (
    CacheManager,
    make_stt_key,
    make_translate_key,
)
from voxstream.pipeline.transcribe import transcribe_chunk
from voxstream.pipeline.translate import translate_segments
from voxstream.providers.base import SttProvider, TranslateProvider


class LookaheadScheduler:
    """Orchestrates rolling look-ahead processing ahead of the video playhead."""

    def __init__(
        self,
        playhead_fn: Callable[[], float],
        chunks: list[ChunkSpec],
        media_id: str,
        media_path: Path,
        cache: CacheManager,
        stt_provider: SttProvider,
        translate_provider: TranslateProvider,
        target_lang: str,
        *,
        source_lang: str | None = None,
        lookahead_seconds: float = 120.0,
        initial_buffer_seconds: float = 20.0,
        pause_on_underrun: bool = True,
    ) -> None:
        self.playhead_fn = playhead_fn
        self.chunks = chunks
        self.media_id = media_id
        self.media_path = media_path
        self.cache = cache
        self.stt_provider = stt_provider
        self.translate_provider = translate_provider
        self.target_lang = target_lang
        self.source_lang = source_lang
        self.lookahead_seconds = lookahead_seconds
        self.initial_buffer_seconds = initial_buffer_seconds
        self.pause_on_underrun = pause_on_underrun

        self.generation: int = 0
        self.chunk_states: dict[int, ChunkState] = {c.index: ChunkState.PENDING for c in chunks}
        self.chunk_results: dict[int, list[TranslatedSegment]] = {}

        self._running = False
        self._is_buffering = False
        self._ready_callbacks: list[Callable[[int, list[TranslatedSegment]], None]] = []
        self._buffering_callbacks: list[Callable[[bool], None]] = []
        self._context_lines: list[str] = []

    def register_chunk_ready_callback(
        self, callback: Callable[[int, list[TranslatedSegment]], None]
    ) -> None:
        self._ready_callbacks.append(callback)

    def register_buffering_callback(self, callback: Callable[[bool], None]) -> None:
        self._buffering_callbacks.append(callback)

    def on_seek(self, new_pos: float) -> None:
        """Handle player seek event: bump generation counter and evaluate buffering."""
        self.generation += 1
        self._check_underrun(new_pos)

    def is_chunk_ready_at(self, playhead_pos: float) -> bool:
        """Check if the chunk covering the current playhead position is READY."""
        for c in self.chunks:
            if c.start <= playhead_pos < c.end:
                return self.chunk_states.get(c.index) == ChunkState.READY
        return True

    def _check_underrun(self, current_pos: float) -> None:
        is_ready = self.is_chunk_ready_at(current_pos)
        if not is_ready:
            if not self._is_buffering:
                self._is_buffering = True
                for cb in self._buffering_callbacks:
                    cb(True)
        else:
            if self._is_buffering:
                self._is_buffering = False
                for cb in self._buffering_callbacks:
                    cb(False)

    async def process_single_chunk(self, chunk: ChunkSpec, task_gen: int) -> None:
        """Process a single chunk with generation validation and cache inspection."""
        stt_key = make_stt_key(self.stt_provider.name, "small", self.source_lang, "30:2")
        trans_key = make_translate_key(
            self.translate_provider.name, "model", self.target_lang, "v1", False
        )

        media_dir = self.cache.get_media_dir(self.media_id)
        audio_dir = media_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        chunk_wav = audio_dir / f"chunk_{chunk.index}.wav"

        # 1. Transcribe (check cache first)
        segments = self.cache.get_transcript(self.media_id, chunk.index, stt_key)
        if segments is None:
            from voxstream.media.extract import extract_audio_chunk

            extract_audio_chunk(
                self.media_path,
                chunk_wav,
                start_seconds=chunk.extraction_start,
                duration_seconds=chunk.extraction_duration,
            )
            segments = await transcribe_chunk(
                self.stt_provider,
                chunk_wav,
                chunk,
                self.media_id,
                language=self.source_lang,
            )
            self.cache.set_transcript(self.media_id, chunk.index, stt_key, segments)

        # Discard if generation went stale
        if task_gen != self.generation:
            return

        self.chunk_states[chunk.index] = ChunkState.TRANSCRIBED

        # 2. Translate (check cache first)
        translations = self.cache.get_translation(
            self.media_id, chunk.index, trans_key, self.target_lang
        )
        if translations is None:
            translations = await translate_segments(
                self.translate_provider,
                segments,
                target_lang=self.target_lang,
                source_lang=self.source_lang,
                context=self._context_lines,
                for_dubbing=False,
            )
            self.cache.set_translation(
                self.media_id, chunk.index, trans_key, self.target_lang, translations
            )

        # Discard if generation went stale
        if task_gen != self.generation:
            return

        self.chunk_states[chunk.index] = ChunkState.READY
        self.chunk_results[chunk.index] = translations
        self._context_lines.extend([t.text for t in translations[-3:]])

        # Notify subscribers
        for cb in self._ready_callbacks:
            cb(chunk.index, translations)

        self._check_underrun(self.playhead_fn())

    async def step(self) -> None:
        """Inspect playhead position and schedule chunks covering [playhead, playhead + lookahead]."""
        pos = self.playhead_fn()
        self._check_underrun(pos)

        window_start = pos
        window_end = pos + self.lookahead_seconds

        # Find chunks overlapping the active lookahead window
        window_chunks = [
            c for c in self.chunks if not (c.end <= window_start or c.start >= window_end)
        ]

        # Prioritize chunks nearest to current playhead
        window_chunks.sort(key=lambda c: abs(c.start - pos))

        for chunk in window_chunks:
            if self.chunk_states[chunk.index] == ChunkState.PENDING:
                curr_gen = self.generation
                await self.process_single_chunk(chunk, curr_gen)
                break  # Process sequentially or with backpressure
