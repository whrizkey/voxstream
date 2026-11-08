"""Provider registry, discovery, and instantiation factories."""

import importlib.util
import shutil
from dataclasses import dataclass
from typing import Literal

from voxstream.config import get_settings
from voxstream.errors import ConfigurationError
from voxstream.providers.base import SttProvider, TranslateProvider, TtsProvider
from voxstream.providers.stt.fake import FakeSttProvider
from voxstream.providers.stt.faster_whisper import FasterWhisperSttProvider
from voxstream.providers.stt.openai_compat import OpenAiCompatSttProvider
from voxstream.providers.translate.anthropic import AnthropicTranslateProvider
from voxstream.providers.translate.deepl import DeepLTranslateProvider
from voxstream.providers.translate.fake import FakeTranslateProvider
from voxstream.providers.translate.openai_compat import OpenAiCompatTranslateProvider
from voxstream.providers.tts.edge import EdgeTtsProvider
from voxstream.providers.tts.elevenlabs import ElevenLabsTtsProvider
from voxstream.providers.tts.fake import FakeTtsProvider
from voxstream.providers.tts.openai import OpenAiTtsProvider
from voxstream.providers.tts.piper import PiperTtsProvider


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
        elif name in ("openai_compat", "openai_compat_stt"):
            has_key = bool(
                settings.openai_key_str
                or "localhost" in settings.openai_base_url
                or "127.0.0.1" in settings.openai_base_url
            )
            return ProviderStatus(
                name=name,
                kind=kind,
                is_usable=has_key,
                reason=None if has_key else "OPENAI_API_KEY not configured",
            )
    elif kind == "translate":
        if name == "openai_compat":
            has_key = bool(
                settings.openai_key_str
                or "localhost" in settings.openai_base_url
                or "127.0.0.1" in settings.openai_base_url
            )
            return ProviderStatus(
                name=name,
                kind=kind,
                is_usable=has_key,
                reason=None if has_key else "OPENAI_API_KEY not configured",
            )
        elif name == "anthropic":
            has_key = bool(settings.anthropic_key_str)
            return ProviderStatus(
                name=name,
                kind=kind,
                is_usable=has_key,
                reason=None if has_key else "ANTHROPIC_API_KEY not configured",
            )
        elif name == "deepl":
            has_key = bool(settings.deepl_key_str)
            return ProviderStatus(
                name=name,
                kind=kind,
                is_usable=has_key,
                reason=None if has_key else "DEEPL_API_KEY not configured",
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
        elif name == "openai":
            has_key = bool(settings.openai_key_str)
            return ProviderStatus(
                name=name,
                kind=kind,
                is_usable=has_key,
                reason=None if has_key else "OPENAI_API_KEY not configured",
            )
        elif name == "elevenlabs":
            has_key = bool(settings.elevenlabs_key_str)
            return ProviderStatus(
                name=name,
                kind=kind,
                is_usable=has_key,
                reason=None if has_key else "ELEVENLABS_API_KEY not configured",
            )
        elif name == "piper":
            has_bin = shutil.which("piper") is not None
            return ProviderStatus(
                name=name,
                kind=kind,
                is_usable=has_bin,
                reason=None if has_bin else "piper binary not found on PATH",
            )

    return ProviderStatus(name=name, kind=kind, is_usable=False, reason="Unknown provider")


def available_providers(kind: Literal["stt", "translate", "tts"]) -> list[ProviderStatus]:
    names_by_kind = {
        "stt": ["faster_whisper", "openai_compat", "fake"],
        "translate": ["openai_compat", "anthropic", "deepl", "fake"],
        "tts": ["edge", "openai", "elevenlabs", "piper", "fake"],
    }
    return [check_provider_usable(kind, n) for n in names_by_kind.get(kind, [])]


def get_stt_provider(name: str | None = None) -> SttProvider:
    settings = get_settings()
    provider_name = name or settings.stt_provider
    if provider_name == "openai_compat_stt":
        provider_name = "openai_compat"

    if provider_name == "fake":
        return FakeSttProvider()
    elif provider_name == "faster_whisper":
        return FasterWhisperSttProvider(model_size=settings.stt_model)
    elif provider_name == "openai_compat":
        return OpenAiCompatSttProvider(
            api_key=settings.openai_key_str,
            base_url=settings.openai_base_url,
            model=settings.stt_model,
        )
    else:
        raise ConfigurationError(f"Unsupported STT provider: {provider_name}")


def get_translate_provider(name: str | None = None) -> TranslateProvider:
    settings = get_settings()
    provider_name = name or settings.translate_provider

    if provider_name == "fake":
        return FakeTranslateProvider()
    elif provider_name == "openai_compat":
        return OpenAiCompatTranslateProvider(
            api_key=settings.openai_key_str,
            base_url=settings.openai_base_url,
            model=settings.translate_model,
        )
    elif provider_name == "anthropic":
        return AnthropicTranslateProvider(
            api_key=settings.anthropic_key_str,
        )
    elif provider_name == "deepl":
        return DeepLTranslateProvider(
            api_key=settings.deepl_key_str,
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
    elif provider_name == "openai":
        return OpenAiTtsProvider(
            api_key=settings.openai_key_str,
            base_url=settings.openai_base_url,
        )
    elif provider_name == "elevenlabs":
        return ElevenLabsTtsProvider(
            api_key=settings.elevenlabs_key_str,
        )
    elif provider_name == "piper":
        return PiperTtsProvider()
    else:
        raise ConfigurationError(f"Unsupported TTS provider: {provider_name}")
