"""Unit tests for language speaking rates."""

from voxstream.languages import DEFAULT_CHARS_PER_SECOND, get_speaking_rate


def test_speaking_rate_lookup() -> None:
    assert get_speaking_rate("en") == 15.0
    assert get_speaking_rate("es") == 16.0
    assert get_speaking_rate("ja") == 8.0
    assert get_speaking_rate("zh") == 5.0
    # Case insensitivity & subtag handling
    assert get_speaking_rate("EN-US") == 15.0
    # Fallback to default
    assert get_speaking_rate("unknown-lang") == DEFAULT_CHARS_PER_SECOND
