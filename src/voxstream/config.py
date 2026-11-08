"""Application configuration and settings management."""

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_env_file() -> Path | None:
    """Resolve .env location safely without reading arbitrary untrusted cwd folders."""
    # 1. Explicit override via env
    explicit = os.environ.get("VOXSTREAM_ENV_FILE")
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None

    # 2. User home config ~/.config/voxstream/.env
    user_env = Path.home() / ".config" / "voxstream" / ".env"
    if user_env.is_file():
        return user_env

    # 3. Git repo root (only if .git directory is present)
    cwd = Path.cwd()
    if (cwd / ".git").is_dir() and (cwd / ".env").is_file():
        return cwd / ".env"

    return None


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_prefix="VOXSTREAM_",
        env_file=_resolve_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider selection
    stt_provider: Literal["faster_whisper", "openai_compat", "openai_compat_stt", "fake"] = (
        "faster_whisper"
    )
    translate_provider: Literal["openai_compat", "anthropic", "deepl", "fake"] = "openai_compat"
    tts_provider: Literal["edge", "openai", "elevenlabs", "piper", "fake"] = "edge"

    @field_validator("stt_provider", mode="before")
    @classmethod
    def _normalize_stt_provider(cls, v: Any) -> str:
        if v == "openai_compat_stt":
            return "openai_compat"
        return str(v)

    # API Keys & URLs with SecretStr masking and dual aliases
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "VOXSTREAM_OPENAI_API_KEY", "OPENAI_API_KEY", "openai_api_key"
        ),
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices(
            "VOXSTREAM_OPENAI_BASE_URL", "OPENAI_BASE_URL", "openai_base_url"
        ),
    )
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "VOXSTREAM_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY", "anthropic_api_key"
        ),
    )
    deepl_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("VOXSTREAM_DEEPL_API_KEY", "DEEPL_API_KEY", "deepl_api_key"),
    )
    elevenlabs_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "VOXSTREAM_ELEVENLABS_API_KEY", "ELEVENLABS_API_KEY", "elevenlabs_api_key"
        ),
    )

    # Models & Voice overrides
    stt_model: str = Field(
        default="small",
        validation_alias=AliasChoices(
            "VOXSTREAM_STT_MODEL",
            "VOXSTREAM_WHISPER_MODEL",
            "STT_MODEL",
            "WHISPER_MODEL",
            "stt_model",
        ),
    )
    translate_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices(
            "VOXSTREAM_TRANSLATE_MODEL",
            "VOXSTREAM_OPENAI_MODEL",
            "TRANSLATE_MODEL",
            "OPENAI_MODEL",
            "translate_model",
        ),
    )
    tts_voice: str | None = None

    # Cost ceiling
    max_cost_usd: float | None = Field(
        default=None,
        validation_alias=AliasChoices("VOXSTREAM_MAX_COST_USD", "MAX_COST_USD", "max_cost_usd"),
    )

    # Pipeline behavior
    lookahead_seconds: float = 120.0
    initial_buffer_seconds: float = 20.0
    chunk_seconds: float = 30.0
    chunk_overlap_seconds: float = 2.0
    max_speedup: float = 1.25
    duck_db: float = -14.0
    pause_on_underrun: bool = True
    cache_dir: Path | None = None

    @property
    def openai_key_str(self) -> str | None:
        return self.openai_api_key.get_secret_value() if self.openai_api_key else None

    @property
    def anthropic_key_str(self) -> str | None:
        return self.anthropic_api_key.get_secret_value() if self.anthropic_api_key else None

    @property
    def deepl_key_str(self) -> str | None:
        return self.deepl_api_key.get_secret_value() if self.deepl_api_key else None

    @property
    def elevenlabs_key_str(self) -> str | None:
        return self.elevenlabs_api_key.get_secret_value() if self.elevenlabs_api_key else None

    def get_cache_path(self) -> Path:
        """Resolve effective cache directory path."""
        if self.cache_dir:
            return self.cache_dir
        # Default to ~/.cache/voxstream on Linux/macOS or %LOCALAPPDATA%/voxstream on Windows
        return Path.home() / ".cache" / "voxstream"


def get_settings() -> Settings:
    """Load settings instance."""
    return Settings()
