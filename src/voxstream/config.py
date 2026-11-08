"""Application configuration and settings management."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_prefix="VOXSTREAM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider selection
    stt_provider: Literal["faster_whisper", "openai_compat", "fake"] = "faster_whisper"
    translate_provider: Literal["openai_compat", "anthropic", "deepl", "fake"] = "openai_compat"
    tts_provider: Literal["edge", "openai", "elevenlabs", "piper", "fake"] = "edge"

    # API Keys & URLs (direct env vars without VOXSTREAM_ prefix allowed via Field validation)
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    deepl_api_key: str | None = Field(default=None, alias="DEEPL_API_KEY")
    elevenlabs_api_key: str | None = Field(default=None, alias="ELEVENLABS_API_KEY")

    # Models & Voice overrides
    stt_model: str = "small"
    translate_model: str = "gpt-4o-mini"
    tts_voice: str | None = None

    # Pipeline behavior
    lookahead_seconds: float = 120.0
    initial_buffer_seconds: float = 20.0
    chunk_seconds: float = 30.0
    chunk_overlap_seconds: float = 2.0
    max_speedup: float = 1.25
    duck_db: float = -14.0
    pause_on_underrun: bool = True
    cache_dir: Path | None = None

    def get_cache_path(self) -> Path:
        """Resolve effective cache directory path."""
        if self.cache_dir:
            return self.cache_dir
        # Default to ~/.cache/voxstream on Linux/macOS or %LOCALAPPDATA%/voxstream on Windows
        return Path.home() / ".cache" / "voxstream"


def get_settings() -> Settings:
    """Load settings instance."""
    return Settings()
