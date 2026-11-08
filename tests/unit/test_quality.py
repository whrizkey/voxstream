"""Unit tests for quality enhancements: diarization, separation, glossary, ASS export, and streams."""

import json
from pathlib import Path

import pytest

from voxstream.export.ass import _format_ass_timestamp, export_ass
from voxstream.export.srt import export_dual_srt
from voxstream.media.stream import is_stream_url
from voxstream.models import Segment, TranslatedSegment
from voxstream.pipeline.diarize import FakeDiarizer, SpeakerTurn, assign_speakers
from voxstream.pipeline.glossary import Glossary
from voxstream.pipeline.separation import FakeSeparator
from voxstream.pipeline.translate import translate_segments
from voxstream.providers.accounting import load_pricing_rates
from voxstream.providers.translate.fake import FakeTranslateProvider


def test_format_ass_timestamp() -> None:
    assert _format_ass_timestamp(0.0) == "0:00:00.00"
    assert _format_ass_timestamp(1.5) == "0:00:01.50"
    assert _format_ass_timestamp(65.123) == "0:01:05.12"
    assert _format_ass_timestamp(3661.05) == "1:01:01.05"


def test_glossary_replacement_and_case() -> None:
    glossary = Glossary.from_dict(
        {
            "warp drive": "motor de curvatura",
            "starfleet": "flota estelar",
        }
    )

    # Lowercase match
    assert glossary.apply("Engage the warp drive.") == "Engage the motor de curvatura."

    # Titlecase match
    assert (
        glossary.apply("Welcome to Starfleet headquarters.")
        == "Welcome to Flota estelar headquarters."
    )

    # Uppercase match
    assert glossary.apply("ALL HAIL STARFLEET!") == "ALL HAIL FLOTA ESTELAR!"

    # Prompt hints
    hints = glossary.get_prompt_hints()
    assert "warp drive" in hints
    assert "motor de curvatura" in hints


def test_glossary_file_loading(tmp_path: Path) -> None:
    json_path = tmp_path / "glossary.json"
    json_path.write_text(json.dumps({"AI": "IA", "computer": "computadora"}))
    g_json = Glossary.from_file(json_path)
    assert g_json.apply("The AI responded.") == "The IA responded."

    csv_path = tmp_path / "glossary.csv"
    csv_path.write_text("hello,hola\nworld,mundo\n")
    g_csv = Glossary.from_file(csv_path)
    assert g_csv.apply("hello world") == "hola mundo"


@pytest.mark.asyncio
async def test_speaker_diarization_attribution() -> None:
    diarizer = FakeDiarizer(
        turns=[
            SpeakerTurn(speaker_id="SPEAKER_00", start=0.0, end=4.0),
            SpeakerTurn(speaker_id="SPEAKER_01", start=4.0, end=8.0),
        ]
    )
    turns = await diarizer.diarize(Path("dummy.wav"))
    assert len(turns) == 2

    segments = [
        Segment(chunk_index=0, seg_id="s1", start=0.5, end=2.5, text="Hello Alice", language="en"),
        Segment(chunk_index=0, seg_id="s2", start=4.5, end=7.0, text="Hi Bob", language="en"),
        Segment(chunk_index=0, seg_id="s3", start=9.0, end=10.0, text="Late cue", language="en"),
    ]

    assigned = assign_speakers(segments, turns)
    assert assigned[0].speaker == "SPEAKER_00"
    assert assigned[1].speaker == "SPEAKER_01"
    # s3 (9.0-10.0) is nearest to SPEAKER_01 (4.0-8.0)
    assert assigned[2].speaker == "SPEAKER_01"


@pytest.mark.asyncio
async def test_audio_separation_fake(tmp_path: Path) -> None:
    separator = FakeSeparator()
    vocals, bgm = await separator.separate(Path("input.wav"), tmp_path)
    assert vocals.exists()
    assert bgm.exists()
    assert vocals.stat().st_size > 0
    assert bgm.stat().st_size > 0


def test_export_ass_subtitles(tmp_path: Path) -> None:
    seg1 = Segment(
        chunk_index=0, seg_id="s1", start=1.0, end=3.5, text="Hello world", language="en"
    )
    seg2 = Segment(
        chunk_index=0, seg_id="s2", start=4.0, end=6.0, text="Second line", language="en"
    )
    translated = [
        TranslatedSegment(seg=seg1, target_lang="es", text="Hola mundo", provider="fake"),
        TranslatedSegment(seg=seg2, target_lang="es", text="Segunda línea", provider="fake"),
    ]

    # Standard preset
    ass_path = tmp_path / "subs.ass"
    export_ass(translated, ass_path, style="anime")
    content = ass_path.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "Style: Anime" in content
    assert "Dialogue: 0,0:00:01.00,0:00:03.50,Anime,,0,0,0,,Hola mundo" in content

    # Dual subtitles
    dual_ass_path = tmp_path / "dual_subs.ass"
    export_ass(translated, dual_ass_path, dual=True)
    dual_content = dual_ass_path.read_text(encoding="utf-8")
    assert "Style: DualTop" in dual_content
    assert "Style: DualBottom" in dual_content
    assert "Dialogue: 0,0:00:01.00,0:00:03.50,DualTop,,0,0,0,,Hello world" in dual_content
    assert "Dialogue: 0,0:00:01.00,0:00:03.50,DualBottom,,0,0,0,,Hola mundo" in dual_content


def test_export_dual_srt(tmp_path: Path) -> None:
    seg = Segment(chunk_index=0, seg_id="s1", start=1.0, end=3.0, text="Hello world", language="en")
    trans = [TranslatedSegment(seg=seg, target_lang="es", text="Hola mundo", provider="fake")]
    srt_path = tmp_path / "dual.srt"
    export_dual_srt(trans, srt_path)

    content = srt_path.read_text(encoding="utf-8")
    assert "Hello world\nHola mundo" in content


def test_stream_url_detection() -> None:
    assert is_stream_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert is_stream_url(
        "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
    )
    assert not is_stream_url("/home/antigravity/video.mp4")
    assert not is_stream_url("C:\\videos\\sample.mkv")


@pytest.mark.asyncio
async def test_translate_with_glossary_and_two_pass() -> None:
    provider = FakeTranslateProvider(prefix="[TR] ")
    segments = [
        Segment(
            chunk_index=0,
            seg_id="s1",
            start=0.0,
            end=2.0,
            text="Activate the warp drive now",
            language="en",
        ),
    ]
    glossary = Glossary.from_dict({"warp drive": "motor de curvatura"})

    results = await translate_segments(
        provider=provider,
        segments=segments,
        target_lang="es",
        glossary=glossary,
        two_pass=True,
    )

    assert len(results) == 1
    assert "motor de curvatura" in results[0].text


def test_pricing_toml_loading(tmp_path: Path) -> None:
    pricing_file = tmp_path / "test_pricing.toml"
    pricing_file.write_text(
        """
[pricing]
elevenlabs = 0.000250
openai_tts = 0.000020
"""
    )
    rates = load_pricing_rates(custom_file=pricing_file)
    assert rates["elevenlabs"] == 0.000250
    assert rates["openai_tts"] == 0.000020
    # Fallback to default
    assert rates["openai_compat"] == 0.0006 / 1000.0
