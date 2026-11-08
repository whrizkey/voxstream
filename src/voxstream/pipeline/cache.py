"""SQLite and filesystem cache for media segments, transcripts, and dub clips."""

import hashlib
import json
import sqlite3
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from voxstream.models import Segment, TranslatedSegment


class CacheManager:
    """Manages SQLite metadata storage and cached audio files."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / "voxstream.db"
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def close(self) -> None:
        """Checkpoint WAL to release locks and close resources."""
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=20.0)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.close()
        except Exception:
            pass

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS media (
                    media_id TEXT PRIMARY KEY,
                    path TEXT,
                    duration REAL,
                    created_at REAL,
                    last_used_at REAL
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    media_id TEXT,
                    chunk_index INTEGER,
                    plan_hash TEXT,
                    start REAL,
                    end REAL,
                    state TEXT,
                    PRIMARY KEY(media_id, chunk_index, plan_hash)
                );

                CREATE TABLE IF NOT EXISTS transcripts (
                    media_id TEXT,
                    chunk_index INTEGER,
                    stt_key TEXT,
                    json_data TEXT,
                    PRIMARY KEY(media_id, chunk_index, stt_key)
                );

                CREATE TABLE IF NOT EXISTS translations (
                    media_id TEXT,
                    chunk_index INTEGER,
                    translate_key TEXT,
                    target_lang TEXT,
                    json_data TEXT,
                    PRIMARY KEY(media_id, chunk_index, translate_key, target_lang)
                );

                CREATE TABLE IF NOT EXISTS clips (
                    media_id TEXT,
                    seg_id TEXT,
                    tts_key TEXT,
                    voice TEXT,
                    lang TEXT,
                    path TEXT,
                    duration REAL,
                    speed_factor REAL,
                    flags TEXT,
                    PRIMARY KEY(media_id, seg_id, tts_key)
                );

                CREATE TABLE IF NOT EXISTS calibration (
                    provider TEXT,
                    voice TEXT,
                    lang TEXT,
                    chars_per_sec REAL,
                    samples INTEGER,
                    PRIMARY KEY(provider, voice, lang)
                );
                """
            )

    def record_media(self, media_id: str, path: str, duration: float) -> None:
        now = time.time()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO media (media_id, path, duration, created_at, last_used_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(media_id) DO UPDATE SET
                    path=excluded.path,
                    duration=excluded.duration,
                    last_used_at=excluded.last_used_at
                """,
                (media_id, path, duration, now, now),
            )

    def touch_media(self, media_id: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE media SET last_used_at = ? WHERE media_id = ?",
                (time.time(), media_id),
            )

    def get_transcript(self, media_id: str, chunk_index: int, stt_key: str) -> list[Segment] | None:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT json_data FROM transcripts WHERE media_id=? AND chunk_index=? AND stt_key=?",
                (media_id, chunk_index, stt_key),
            ).fetchone()
            if not row:
                return None
            try:
                data = json.loads(row["json_data"])
                return [Segment(**item) for item in data]
            except Exception:
                return None

    def set_transcript(
        self,
        media_id: str,
        chunk_index: int,
        stt_key: str,
        segments: list[Segment],
    ) -> None:
        payload = json.dumps([asdict(s) for s in segments])
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO transcripts (media_id, chunk_index, stt_key, json_data)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(media_id, chunk_index, stt_key) DO UPDATE SET
                    json_data=excluded.json_data
                """,
                (media_id, chunk_index, stt_key, payload),
            )

    def get_translation(
        self,
        media_id: str,
        chunk_index: int,
        translate_key: str,
        target_lang: str,
    ) -> list[TranslatedSegment] | None:
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT json_data FROM translations
                WHERE media_id=? AND chunk_index=? AND translate_key=? AND target_lang=?
                """,
                (media_id, chunk_index, translate_key, target_lang),
            ).fetchone()
            if not row:
                return None
            try:
                data = json.loads(row["json_data"])
                results: list[TranslatedSegment] = []
                for item in data:
                    seg_dict = item["seg"]
                    seg = Segment(**seg_dict)
                    results.append(
                        TranslatedSegment(
                            seg=seg,
                            target_lang=item["target_lang"],
                            text=item["text"],
                            provider=item["provider"],
                        )
                    )
                return results
            except Exception:
                return None

    def set_translation(
        self,
        media_id: str,
        chunk_index: int,
        translate_key: str,
        target_lang: str,
        translations: list[TranslatedSegment],
    ) -> None:
        payload = json.dumps([asdict(t) for t in translations])
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO translations (media_id, chunk_index, translate_key, target_lang, json_data)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(media_id, chunk_index, translate_key, target_lang) DO UPDATE SET
                    json_data=excluded.json_data
                """,
                (media_id, chunk_index, translate_key, target_lang, payload),
            )

    def get_media_dir(self, media_id: str) -> Path:
        media_dir = self.cache_dir / media_id
        media_dir.mkdir(parents=True, exist_ok=True)
        return media_dir

    def get_stats(self) -> dict[str, Any]:
        with self._get_connection() as conn:
            media_count = conn.execute("SELECT count(*) as c FROM media").fetchone()["c"]
            transcript_count = conn.execute("SELECT count(*) as c FROM transcripts").fetchone()["c"]
            translation_count = conn.execute("SELECT count(*) as c FROM translations").fetchone()[
                "c"
            ]
            clip_count = conn.execute("SELECT count(*) as c FROM clips").fetchone()["c"]

        # Calculate on-disk storage size
        total_size = sum(f.stat().st_size for f in self.cache_dir.rglob("*") if f.is_file())
        return {
            "media_count": media_count,
            "transcripts_count": transcript_count,
            "translations_count": translation_count,
            "clips_count": clip_count,
            "total_bytes": total_size,
            "db_path": str(self.db_path),
        }

    def clear(self, media_id: str | None = None) -> None:
        with self._get_connection() as conn:
            if media_id:
                conn.execute("DELETE FROM media WHERE media_id=?", (media_id,))
                conn.execute("DELETE FROM chunks WHERE media_id=?", (media_id,))
                conn.execute("DELETE FROM transcripts WHERE media_id=?", (media_id,))
                conn.execute("DELETE FROM translations WHERE media_id=?", (media_id,))
                conn.execute("DELETE FROM clips WHERE media_id=?", (media_id,))
                media_path = self.cache_dir / media_id
                if media_path.exists():
                    import shutil

                    shutil.rmtree(media_path, ignore_errors=True)
            else:
                conn.execute("DELETE FROM media")
                conn.execute("DELETE FROM chunks")
                conn.execute("DELETE FROM transcripts")
                conn.execute("DELETE FROM translations")
                conn.execute("DELETE FROM clips")


def make_stt_key(provider_name: str, model: str, language: str | None, chunk_params: str) -> str:
    raw = f"{provider_name}:{model}:{language or 'auto'}:{chunk_params}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def make_translate_key(
    provider_name: str, model: str, target_lang: str, prompt_version: str, max_chars_mode: bool
) -> str:
    raw = f"{provider_name}:{model}:{target_lang}:{prompt_version}:{max_chars_mode}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
