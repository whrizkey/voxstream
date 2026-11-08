"""Unit tests for SQLite CacheManager."""

import tempfile
from pathlib import Path

from voxstream.models import Segment, TranslatedSegment
from voxstream.pipeline.cache import (
    CacheManager,
    make_stt_key,
    make_translate_key,
)


def test_cache_manager_crud() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        cache = CacheManager(Path(tmp_dir))
        media_id = "test_media_999"

        cache.record_media(media_id, "/path/to/vid.mp4", 120.0)
        cache.touch_media(media_id)

        stt_key = make_stt_key("fake", "model", "en", "30:2")
        # Initially miss
        assert cache.get_transcript(media_id, 0, stt_key) is None

        # Write transcript
        segs = [
            Segment(
                chunk_index=0,
                seg_id="seg1",
                start=1.0,
                end=3.0,
                text="Hello",
                language="en",
            )
        ]
        cache.set_transcript(media_id, 0, stt_key, segs)

        # Hit
        loaded = cache.get_transcript(media_id, 0, stt_key)
        assert loaded is not None
        assert len(loaded) == 1
        assert loaded[0].text == "Hello"

        # Translation cache
        trans_key = make_translate_key("fake", "model", "es", "v1", False)
        assert cache.get_translation(media_id, 0, trans_key, "es") is None

        tsegs = [
            TranslatedSegment(
                seg=segs[0],
                target_lang="es",
                text="Hola",
                provider="fake",
            )
        ]
        cache.set_translation(media_id, 0, trans_key, "es", tsegs)

        loaded_trans = cache.get_translation(media_id, 0, trans_key, "es")
        assert loaded_trans is not None
        assert loaded_trans[0].text == "Hola"

        # Stats
        stats = cache.get_stats()
        assert stats["media_count"] == 1
        assert stats["transcripts_count"] == 1
        assert stats["translations_count"] == 1

        # Clear
        cache.clear(media_id)
        assert cache.get_transcript(media_id, 0, stt_key) is None
