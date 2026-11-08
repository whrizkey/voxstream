"""Shared contract compliance tests for STT, Translation, and TTS providers."""

import json
from typing import Any

import httpx
import pytest

from voxstream.providers.base import (
    SttProvider,
    TranslateItem,
    TtsProvider,
)
from voxstream.providers.registry import available_providers
from voxstream.providers.stt.fake import FakeSttProvider
from voxstream.providers.translate.anthropic import AnthropicTranslateProvider
from voxstream.providers.translate.deepl import DeepLTranslateProvider
from voxstream.providers.tts.fake import FakeTtsProvider


@pytest.mark.parametrize("provider", [FakeSttProvider()])
def test_stt_provider_protocol(provider: SttProvider) -> None:
    assert isinstance(provider, SttProvider)
    assert hasattr(provider, "transcribe")
    assert hasattr(provider, "name")


@pytest.mark.asyncio
async def test_anthropic_contract_with_mock() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        data = [{"id": "item1", "text": "Bonjour le monde"}]
        return httpx.Response(
            200,
            json={"content": [{"text": json.dumps(data)}]},
        )

    provider = AnthropicTranslateProvider(api_key="mock-key")
    # Patch httpx.AsyncClient with mock transport
    orig_post = httpx.AsyncClient.post

    async def mock_post(self: httpx.AsyncClient, *args: Any, **kwargs: Any) -> httpx.Response:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as c:
            return await orig_post(c, *args, **kwargs)

    httpx.AsyncClient.post = mock_post  # type: ignore
    try:
        items = [TranslateItem(id="item1", text="Hello world")]
        res = await provider.translate(items, source_lang="en", target_lang="fr", context=[])
        assert len(res) == 1
        assert res[0].id == "item1"
        assert res[0].text == "Bonjour le monde"
    finally:
        httpx.AsyncClient.post = orig_post  # type: ignore


@pytest.mark.asyncio
async def test_deepl_contract_with_mock() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"translations": [{"text": "Hallo Welt"}]},
        )

    provider = DeepLTranslateProvider(api_key="mock-key")
    orig_post = httpx.AsyncClient.post

    async def mock_post_deepl(self: httpx.AsyncClient, *args: Any, **kwargs: Any) -> httpx.Response:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as c:
            return await orig_post(c, *args, **kwargs)

    httpx.AsyncClient.post = mock_post_deepl  # type: ignore
    try:
        items = [TranslateItem(id="item1", text="Hello world")]
        res = await provider.translate(items, source_lang="en", target_lang="de", context=[])
        assert len(res) == 1
        assert res[0].id == "item1"
        assert res[0].text == "Hallo Welt"
    finally:
        httpx.AsyncClient.post = orig_post  # type: ignore


@pytest.mark.parametrize("provider", [FakeTtsProvider()])
def test_tts_provider_protocol(provider: TtsProvider) -> None:
    assert isinstance(provider, TtsProvider)
    assert hasattr(provider, "synthesize")
    assert hasattr(provider, "list_voices")
    voices = provider.list_voices("en")
    assert len(voices) > 0


def test_registry_availability_listing() -> None:
    stt_list = available_providers("stt")
    assert any(p.name == "fake" and p.is_usable for p in stt_list)

    trans_list = available_providers("translate")
    assert any(p.name == "fake" and p.is_usable for p in trans_list)
    assert any(p.name == "anthropic" for p in trans_list)
    assert any(p.name == "deepl" for p in trans_list)

    tts_list = available_providers("tts")
    assert any(p.name == "fake" and p.is_usable for p in tts_list)
    assert any(p.name == "elevenlabs" for p in tts_list)
    assert any(p.name == "piper" for p in tts_list)
