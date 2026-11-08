"""Provider registry, discovery, and instantiation factories."""

import importlib.util
from dataclasses import dataclass
from typing import Literal

from voxstream.config import get_settings
from voxstream.errors import ConfigurationError
from voxstream.providers.base import SttProvider, TranslateProvider, TtsProvider
from voxstream.providers.stt.fake import FakeSttProvider
from voxstream.providers.stt.faster_whisper import FasterWhisperSttProvider
from voxstream.providers.translate.fake import FakeTranslateProvider
from voxstream.providers.translate.openai_compat import OpenAiCompatTranslateProvider
from voxstream.providers.tts.edge import EdgeTtsProvider
from voxstream.providers.tts.fake import FakeTtsProvider


@dataclass(frozen=True)
class ProviderStatus:
    name: str
    kind: Literal["stt", "translate", "tts"]
    is_usable: bool
    reason: str | None = None


def check_provider_usable(kind: Literal["stt", "translate", "tts"], name: str) -> ProviderStatus:
    settings = get_settings()
    if name == "fake":
        return ProviderStatus(name=name, kind=kind, is_usable=True)

    if kind == "stt":
        if name == "faster_whisper":
            has_mod = importlib.util.find_spec("faster_whisper") is not None
            return ProviderStatus(
                name=name,
                kind=kind,
                is_usable=has_mod,
                reason=None if has_mod else "faster-whisper package not installed",
            )
    elif kind == "translate":
        if name == "openai_compat":
            has_key = bool(
                settings.openai_api_key
                or "localhost" in settings.openai_base_url
                or "127.0.0.1" in settings.openai_base_url
            )
            return ProviderStatus(
                name=name,
                kind=kind,
                is_usable=has_key,
                reason=None if has_key else "OPENAI_API_KEY not configured",
            )
    elif kind == "tts":
        if name == "edge":
            has_mod = importlib.util.find_spec("edge_tts") is not None
            return ProviderStatus(
                name=name,
                kind=kind,
                is_usable=has_mod,
                reason=None if has_mod else "edge-tts package not installed",
            )

    return ProviderStatus(name=name, kind=kind, is_usable=False, reason="Unknown provider")


def get_stt_provider(name: str | None = None) -> SttProvider:
    settings = get_settings()
    provider_name = name or settings.stt_provider

    if provider_name == "fake":
        return FakeSttProvider()
    elif provider_name == "faster_whisper":
        return FasterWhisperSttProvider(model_size=settings.stt_model)
    else:
        raise ConfigurationError(f"Unsupported STT provider: {provider_name}")


def get_translate_provider(name: str | None = None) -> TranslateProvider:
    settings = get_settings()
    provider_name = name or settings.translate_provider

    if provider_name == "fake":
        return FakeTranslateProvider()
    elif provider_name == "openai_compat":
        return OpenAiCompatTranslateProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.translate_model,
        )
    else:
        raise ConfigurationError(f"Unsupported translation provider: {provider_name}")


def get_tts_provider(name: str | None = None) -> TtsProvider:
    settings = get_settings()
    provider_name = name or settings.tts_provider

    if provider_name == "fake":
        return FakeTtsProvider()
    elif provider_name == "edge":
        return EdgeTtsProvider()
    else:
        raise ConfigurationError(f"Unsupported TTS provider: {provider_name}")
