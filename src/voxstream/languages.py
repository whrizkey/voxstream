"""Language registry, ISO 639-1 mappings, and baseline speaking-rate heuristics."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageInfo:
    code: str
    name: str
    chars_per_second: float


# Baseline characters-per-second speech rates for common languages.
# Used to calculate max_chars budgets during translation for dubbing.
DEFAULT_SPEAKING_RATES: dict[str, float] = {
    "en": 15.0,  # English
    "es": 16.0,  # Spanish
    "fr": 15.0,  # French
    "de": 14.0,  # German
    "it": 15.0,  # Italian
    "pt": 15.0,  # Portuguese
    "nl": 14.0,  # Dutch
    "id": 14.0,  # Indonesian
    "ru": 13.0,  # Russian
    "ar": 11.0,  # Arabic
    "hi": 12.0,  # Hindi
    "ja": 8.0,  # Japanese
    "zh": 5.0,  # Chinese (Mandarin)
    "ko": 7.0,  # Korean
}

DEFAULT_CHARS_PER_SECOND = 14.0


def get_speaking_rate(language_code: str) -> float:
    """Return estimated speaking rate (characters per second) for a language."""
    base_code = language_code.lower().split("-")[0]
    return DEFAULT_SPEAKING_RATES.get(base_code, DEFAULT_CHARS_PER_SECOND)
