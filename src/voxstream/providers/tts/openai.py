"""OpenAI TTS provider implementation."""

import tempfile
from pathlib import Path

import httpx

from voxstream.errors import ProviderError
from voxstream.providers.base import Voice, redact_secrets


class OpenAiTtsProvider:
    name = "openai"
    sample_rate = 24000

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "tts-1",
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def list_voices(self, lang: str) -> list[Voice]:
        voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        return [Voice(id=v, name=v.capitalize(), lang=lang) for v in voices]

    async def synthesize(
        self,
        text: str,
        *,
        lang: str,
        voice: str | None = None,
        rate: float = 1.0,
    ) -> Path:
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY is not set", provider=self.name, retryable=False)

        url = f"{self.base_url}/audio/speech"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        chosen_voice = voice or "alloy"
        payload = {
            "model": self.model,
            "input": text,
            "voice": chosen_voice,
            "response_format": "wav",
            "speed": max(0.25, min(4.0, rate)),
        }

        tmp_out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        out_path = Path(tmp_out.name)
        tmp_out.close()

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, headers=headers, json=payload, timeout=self.timeout)
            except Exception as exc:
                if out_path.exists():
                    out_path.unlink(missing_ok=True)
                raise ProviderError(
                    redact_secrets(f"Network error: {exc}"), provider=self.name, retryable=True
                ) from exc

        if resp.status_code != 200:
            if out_path.exists():
                out_path.unlink(missing_ok=True)
            raise ProviderError(
                redact_secrets(f"OpenAI TTS error HTTP {resp.status_code}: {resp.text}"),
                provider=self.name,
                retryable=resp.status_code >= 500,
            )

        out_path.write_bytes(resp.content)
        return out_path
