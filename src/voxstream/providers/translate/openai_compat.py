"""OpenAI-compatible translation provider implementing JSON schema contract."""

import json
from typing import Any

import httpx

from voxstream.errors import ProviderError
from voxstream.providers.base import TranslateItem, TranslateResult, redact_secrets


class OpenAiCompatTranslateProvider:
    name = "openai_compat"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _build_system_prompt(self, target_lang: str, context: list[str]) -> str:
        prompt = (
            f"You are a professional spoken-dialogue translator. Translate each input item into {target_lang}.\n"
            "Rules:\n"
            "1. Output valid JSON ONLY. No markdown formatting, no explanations, no wrappers.\n"
            '2. Output format must strictly be a JSON list of objects: [{"id": "<item_id>", "text": "<translated_text>"}].\n'
            "3. Keep proper nouns, numbers, and spoken register natural.\n"
            "4. Do NOT combine, reorder, or omit items.\n"
            "5. If 'max_chars' is specified, your translation must be equal to or shorter than that character count. Use concise paraphrasing if needed.\n"
        )
        if context:
            prompt += "Preceding conversation context for tone/continuity:\n" + "\n".join(
                f"- {c}" for c in context[-5:]
            )
        return prompt

    def _parse_response(self, content: str, expected_ids: list[str]) -> list[TranslateResult]:
        clean = content.strip()
        if clean.startswith("```"):
            lines = clean.splitlines()
            if len(lines) >= 2:
                clean = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

        data = json.loads(clean)
        if not isinstance(data, list):
            raise ValueError(f"Expected JSON list, got {type(data)}")

        results_by_id: dict[str, str] = {}
        for item in data:
            if isinstance(item, dict) and "id" in item and "text" in item:
                results_by_id[str(item["id"])] = str(item["text"]).strip()

        # Validate all expected IDs are present
        results: list[TranslateResult] = []
        for expected_id in expected_ids:
            if expected_id not in results_by_id:
                raise ValueError(f"Missing ID in translated output: {expected_id}")
            results.append(TranslateResult(id=expected_id, text=results_by_id[expected_id]))

        return results

    async def _send_request(self, client: httpx.AsyncClient, messages: list[dict[str, str]]) -> str:
        url = f"{self.base_url}/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
        }

        try:
            resp = await client.post(url, headers=headers, json=payload, timeout=self.timeout)
        except httpx.TimeoutException as exc:
            raise ProviderError(
                f"Request timed out after {self.timeout}s", provider=self.name, retryable=True
            ) from exc
        except Exception as exc:
            raise ProviderError(
                redact_secrets(f"Network error: {exc}"),
                provider=self.name,
                retryable=True,
            ) from exc

        if resp.status_code >= 500:
            raise ProviderError(
                f"Server error HTTP {resp.status_code}: {resp.text}",
                provider=self.name,
                retryable=True,
            )
        elif resp.status_code != 200:
            raise ProviderError(
                redact_secrets(f"API error HTTP {resp.status_code}: {resp.text}"),
                provider=self.name,
                retryable=False,
            )

        data = resp.json()
        return str(data["choices"][0]["message"]["content"])

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

        expected_ids = [item.id for item in items]
        input_payload = [
            {
                "id": item.id,
                "text": item.text,
                **({"max_chars": item.max_chars} if item.max_chars else {}),
            }
            for item in items
        ]

        system_prompt = self._build_system_prompt(target_lang, context)
        user_prompt = json.dumps(input_payload, ensure_ascii=False)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        async with httpx.AsyncClient() as client:
            # First attempt
            raw_content = await self._send_request(client, messages)
            try:
                return self._parse_response(raw_content, expected_ids)
            except Exception:
                # Retry once with repair instruction
                repair_messages = list(messages)
                repair_messages.append({"role": "assistant", "content": raw_content})
                repair_messages.append(
                    {
                        "role": "user",
                        "content": 'ERROR: Output could not be parsed. Return ONLY a valid JSON array [{"id": ..., "text": ...}] containing every item.',
                    }
                )
                try:
                    repaired_content = await self._send_request(client, repair_messages)
                    return self._parse_response(repaired_content, expected_ids)
                except Exception as exc:
                    # Final fallback: fall back to item-by-item translation or raise
                    raise ProviderError(
                        redact_secrets(f"Failed to parse translation JSON after retry: {exc}"),
                        provider=self.name,
                        retryable=False,
                    ) from exc
