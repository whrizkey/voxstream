"""DeepL translation provider."""

import httpx

from voxstream.errors import ProviderError
from voxstream.providers.base import TranslateItem, TranslateResult, redact_secrets


class DeepLTranslateProvider:
    name = "deepl"

    def __init__(self, api_key: str | None = None, timeout: float = 60.0) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = (
            "https://api-free.deepl.com/v2/translate"
            if api_key and api_key.endswith(":fx")
            else "https://api.deepl.com/v2/translate"
        )

    async def translate(
        self,
        items: list[TranslateItem],
        *,
        source_lang: str | None,
        target_lang: str,
        context: list[str],
    ) -> list[TranslateResult]:
        if not items:
            return []

        if not self.api_key:
            raise ProviderError("DEEPL_API_KEY is not set", provider=self.name, retryable=False)

        headers = {
            "Authorization": f"DeepL-Auth-Key {self.api_key}",
            "Content-Type": "application/json",
        }

        # DeepL target language codes are uppercase (e.g. EN-US, ES, DE)
        clean_target = target_lang.upper().split("-")[0]
        texts = [item.text for item in items]

        payload = {
            "text": texts,
            "target_lang": clean_target,
        }
        if source_lang:
            payload["source_lang"] = source_lang.upper().split("-")[0]

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    self.base_url, headers=headers, json=payload, timeout=self.timeout
                )
            except Exception as exc:
                raise ProviderError(
                    redact_secrets(f"Network error: {exc}"), provider=self.name, retryable=True
                ) from exc

        if resp.status_code != 200:
            raise ProviderError(
                redact_secrets(f"DeepL API error HTTP {resp.status_code}: {resp.text}"),
                provider=self.name,
                retryable=resp.status_code >= 500,
            )

        data = resp.json()
        translations = data.get("translations", [])
        return [
            TranslateResult(id=item.id, text=translations[i].get("text", item.text))
            for i, item in enumerate(items)
        ]
