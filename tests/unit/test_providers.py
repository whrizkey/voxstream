"""Unit tests for provider protocols, fake providers, and OpenAI compat translator."""

import json
from pathlib import Path

import httpx
import pytest
import soundfile as sf

from voxstream.providers.base import (
    RawSegment,
    TranslateItem,
    redact_secrets,
)
from voxstream.providers.registry import (
    get_stt_provider,
    get_translate_provider,
    get_tts_provider,
)
from voxstream.providers.stt.fake import FakeSttProvider
from voxstream.providers.translate.fake import FakeTranslateProvider
from voxstream.providers.translate.openai_compat import OpenAiCompatTranslateProvider
from voxstream.providers.tts.fake import FakeTtsProvider


def test_secret_redaction() -> None:
    secret = "sk-proj-1234567890abcdefghijklmnopqrstuvwxyz"
    message = f"Error with key: {secret} in request"
    redacted = redact_secrets(message)
    assert secret not in redacted
    assert "[REDACTED_SECRET]" in redacted

    bearer = "Authorization: Bearer secret_token_abcdef1234567890"
    assert "secret_token" not in redact_secrets(bearer)


@pytest.mark.asyncio
async def test_fake_stt_provider() -> None:
    custom_segments = [RawSegment(start=0.0, end=2.0, text="Hello", language="en")]
    stt = FakeSttProvider(fixture_segments=custom_segments)
    result = await stt.transcribe(Path("/dummy/audio.wav"))
    assert len(result) == 1
    assert result[0].text == "Hello"


@pytest.mark.asyncio
async def test_fake_translate_provider() -> None:
    trans = FakeTranslateProvider()
    items = [
        TranslateItem(id="1", text="Hello world"),
        TranslateItem(id="2", text="Long text to clamp", max_chars=10),
    ]
    res = await trans.translate(items, source_lang="en", target_lang="es", context=[])
    assert len(res) == 2
    assert res[0].text == "[es] Hello world"
    assert len(res[1].text) <= 10


@pytest.mark.asyncio
async def test_fake_tts_provider() -> None:
    tts = FakeTtsProvider()
    voices = tts.list_voices("en")
    assert len(voices) > 0

    wav_path = await tts.synthesize("Hello world speech test", lang="en")
    try:
        assert wav_path.exists()
        data, sr = sf.read(str(wav_path))
        assert sr == 24000
        assert len(data) > 0
    finally:
        if wav_path.exists():
            wav_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_openai_compat_translate_mock() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        req_body = json.loads(request.content)
        user_msg = req_body["messages"][-1]["content"]
        items = json.loads(user_msg)
        resp_data = [{"id": item["id"], "text": f"Translated {item['text']}"} for item in items]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(resp_data)}}]},
        )

    class MockedOpenAiProvider(OpenAiCompatTranslateProvider):
        def __init__(self) -> None:
            super().__init__(api_key="test-key", base_url="https://mock.api/v1")
            self.mock_transport = httpx.MockTransport(handler)

        async def _send_request(
            self, client: httpx.AsyncClient, messages: list[dict[str, str]]
        ) -> str:
            async with httpx.AsyncClient(transport=self.mock_transport) as mock_client:
                return await super()._send_request(mock_client, messages)

    provider = MockedOpenAiProvider()
    items = [TranslateItem(id="c1", text="Good morning")]
    res = await provider.translate(items, source_lang="en", target_lang="de", context=[])
    assert len(res) == 1
    assert res[0].id == "c1"
    assert res[0].text == "Translated Good morning"


def test_registry_factories() -> None:
    stt = get_stt_provider("fake")
    assert stt.name == "fake"

    trans = get_translate_provider("fake")
    assert trans.name == "fake"

    tts = get_tts_provider("fake")
    assert tts.name == "fake"


@pytest.mark.asyncio
async def test_edge_tts_voice_selection_with_running_loop() -> None:
    from voxstream.providers.tts.edge import EdgeTtsProvider

    provider = EdgeTtsProvider()
    voices = provider.list_voices("es")
    assert len(voices) > 0
    assert any(
        "es" in v.lang.lower() or "es-" in v.id.lower() or "alvaro" in v.id.lower() for v in voices
    )

    voices_fr = await provider.list_voices_async("fr")
    assert len(voices_fr) > 0
    assert any(
        "fr" in v.lang.lower() or "fr-" in v.id.lower() or "denise" in v.id.lower()
        for v in voices_fr
    )


def test_unusable_provider_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch, sample_wav: Path
) -> None:
    from voxstream.errors import ConfigurationError
    from voxstream.playback.controller import PlaybackController

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("VOXSTREAM_STT_PROVIDER", "openai_compat_stt")

    with pytest.raises(ConfigurationError) as exc_info:
        PlaybackController(
            media_path=sample_wav,
            target_lang="es",
        )
    assert "not usable" in str(exc_info.value)
