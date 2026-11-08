"""Exception hierarchy for VoxStream."""


class VoxStreamError(Exception):
    """Base exception for all VoxStream errors."""


class ConfigurationError(VoxStreamError):
    """Raised when configuration or settings are invalid or missing."""


class MediaError(VoxStreamError):
    """Raised when media probing, extraction, or playback fails."""


class ProviderError(VoxStreamError):
    """Raised when an external or local provider encounters an error."""

    def __init__(self, message: str, *, provider: str, retryable: bool = False) -> None:
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.retryable = retryable


class PipelineError(VoxStreamError):
    """Raised when scheduling or processing within the media pipeline fails."""


class ExternalToolError(VoxStreamError):
    """Raised when an external tool (ffmpeg, ffprobe, demucs, yt-dlp) fails or is missing."""


class BudgetExceededError(VoxStreamError):
    """Raised when estimated usage exceeds the configured max_cost_usd ceiling."""
