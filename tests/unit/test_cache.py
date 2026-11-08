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
        media_id = "0123456789abcdef0123456789abcdef"

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


def test_cache_manager_path_traversal_prevention() -> None:
    import pytest

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        cache = CacheManager(Path(tmp_dir))

        # Relative traversal
        with pytest.raises(ValueError, match="Invalid media_id format"):
            cache.clear("../precious")

        with pytest.raises(ValueError, match="Invalid media_id format"):
            cache.get_media_dir("../precious")

        # Absolute traversal
        with pytest.raises(ValueError, match="Invalid media_id format"):
            cache.clear("/tmp/precious")

        # Non-hex characters
        with pytest.raises(ValueError, match="Invalid media_id format"):
            cache.clear("invalid_media_id_not_32_hex_chars!")


def test_cache_manager_prune() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        cache = CacheManager(Path(tmp_dir))
        m1 = "11111111111111111111111111111111"
        m2 = "22222222222222222222222222222222"

        d1 = cache.get_media_dir(m1)
        d2 = cache.get_media_dir(m2)
        (d1 / "test.bin").write_bytes(b"A" * 1024)
        (d2 / "test.bin").write_bytes(b"B" * 2048)

        cache.record_media(m1, "/p1.mp4", 10.0)
        cache.record_media(m2, "/p2.mp4", 20.0)

        # Prune down to 1500 bytes (should remove m1)
        removed = cache.prune(max_bytes=2500)
        assert removed >= 1
