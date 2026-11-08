"""Fake deterministic translation provider for offline testing."""

from voxstream.providers.base import TranslateItem, TranslateResult


class FakeTranslateProvider:
    name = "fake"

    def __init__(self, prefix: str | None = None) -> None:
        self.prefix = prefix

    async def translate(
        self,
        items: list[TranslateItem],
        *,
        source_lang: str | None,
        target_lang: str,
        context: list[str],
    ) -> list[TranslateResult]:
        results: list[TranslateResult] = []
        for item in items:
            prefix = self.prefix if self.prefix is not None else f"[{target_lang}] "
            translated_text = f"{prefix}{item.text}"
            if item.max_chars and len(translated_text) > item.max_chars:
                # Clamp to max_chars if constraint provided
                translated_text = translated_text[: item.max_chars].rstrip()
            results.append(TranslateResult(id=item.id, text=translated_text))
        return results
