"""Unit tests for SRT formatting and export."""

import tempfile
from pathlib import Path

from voxstream.export.srt import (
    export_srt,
    format_srt_timestamp,
    generate_srt_content,
    wrap_subtitle_text,
)
from voxstream.models import Segment, TranslatedSegment


def test_format_srt_timestamp() -> None:
    assert format_srt_timestamp(0.0) == "00:00:00,000"
    assert format_srt_timestamp(65.123) == "00:01:05,123"
    assert format_srt_timestamp(3661.050) == "01:01:01,050"


def test_wrap_subtitle_text() -> None:
    short_text = "This is a short line."
    assert wrap_subtitle_text(short_text) == short_text

    long_text = "This is a very long line that definitely needs wrapping because it exceeds forty-two characters."
    wrapped = wrap_subtitle_text(long_text, max_chars_per_line=30)
    lines = wrapped.splitlines()
    assert len(lines) <= 2
    assert len(lines[0]) <= 30


def test_generate_and_export_srt() -> None:
    seg = Segment(
        chunk_index=0,
        seg_id="s1",
        start=1.5,
        end=4.2,
        text="Hello world",
        language="en",
    )
    trans = TranslatedSegment(
        seg=seg,
        target_lang="es",
        text="Hola mundo",
        provider="fake",
    )

    content = generate_srt_content([trans])
    assert "1\n00:00:01,500 --> 00:00:04,200\nHola mundo" in content

    # Test dual subtitles
    dual_content = generate_srt_content([trans], dual=True)
    assert "Hello world\nHola mundo" in dual_content

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_file = Path(tmp_dir) / "output.srt"
        export_srt([trans], out_file)
        assert out_file.exists()
        assert out_file.read_text(encoding="utf-8") == content
