"""Unit tests for configuration loading and environment isolation."""

import os
import tempfile
from pathlib import Path

from voxstream.config import _resolve_env_file


def test_resolve_env_file_ignores_cwd() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        fake_cwd = Path(tmp_dir) / "project"
        fake_cwd.mkdir()
        env_file = fake_cwd / ".env"
        env_file.write_text("VOXSTREAM_LOOKAHEAD_SECONDS=999\n", encoding="utf-8")

        # Even with a .git dir in cwd, _resolve_env_file should not load from cwd
        (fake_cwd / ".git").mkdir()

        orig_cwd = Path.cwd()
        try:
            os.chdir(fake_cwd)
            resolved = _resolve_env_file()
            assert resolved != env_file
        finally:
            os.chdir(orig_cwd)


def test_resolve_env_file_honors_explicit_override() -> None:
    with tempfile.NamedTemporaryFile(suffix=".env") as f:
        p = Path(f.name)
        os.environ["VOXSTREAM_ENV_FILE"] = str(p)
        try:
            resolved = _resolve_env_file()
            assert resolved == p
        finally:
            os.environ.pop("VOXSTREAM_ENV_FILE", None)
