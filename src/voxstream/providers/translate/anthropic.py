"""Anthropic Claude translation provider."""

import json
from typing import Any

import httpx

from voxstream.errors import ProviderError
from voxstream.providers.base import TranslateItem, TranslateResult, redact_secrets


class AnthropicTranslateProvider:
    name = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-3-5-haiku-20241022",
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

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
            raise ProviderError("ANTHROPIC_API_KEY is not set", provider=self.name, retryable=False)

        expected_ids = [item.id for item in items]
        input_payload = [
            {
                "id": item.id,
                "text": item.text,
                **({"max_chars": item.max_chars} if item.max_chars else {}),
            }
            for item in items
        ]

        system_prompt = (
            f"You are a professional spoken-dialogue translator. Translate each input item into {target_lang}.\n"
            'Return valid JSON ONLY as an array: [{"id": ..., "text": ...}]. Do NOT add commentary or code blocks.'
        )

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self.model,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": json.dumps(input_payload, ensure_ascii=False)}
            ],
            "max_tokens": 2048,
            "temperature": 0.1,
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
            except Exception as exc:
                raise ProviderError(
                    redact_secrets(f"Network error: {exc}"), provider=self.name, retryable=True
                ) from exc

        if resp.status_code != 200:
            raise ProviderError(
                redact_secrets(f"Anthropic API error HTTP {resp.status_code}: {resp.text}"),
                provider=self.name,
                retryable=resp.status_code >= 500,
            )

        data = resp.json()
        content = data["content"][0]["text"].strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

        parsed = json.loads(content)
        results_map = {str(item["id"]): str(item["text"]) for item in parsed}
        return [TranslateResult(id=eid, text=results_map.get(eid, "")) for eid in expected_ids]
