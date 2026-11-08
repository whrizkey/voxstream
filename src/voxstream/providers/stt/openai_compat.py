"""OpenAI-compatible HTTP Whisper STT provider."""

from pathlib import Path

import httpx

from voxstream.errors import ProviderError
from voxstream.providers.base import RawSegment, redact_secrets


class OpenAiCompatSttProvider:
    name = "openai_compat"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "whisper-1",
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def transcribe(
        self,
        audio: Path,
        *,
        language: str | None = None,
        word_timestamps: bool = False,
    ) -> list[RawSegment]:
        if not audio.exists():
            raise ProviderError(f"Audio file not found: {audio}", provider=self.name)

        url = f"{self.base_url}/audio/transcriptions"
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        data: dict[str, str] = {
            "model": self.model,
            "response_format": "verbose_json",
        }
        if language:
            data["language"] = language.lower().split("-")[0]

        async with httpx.AsyncClient() as client:
            try:
                with open(audio, "rb") as f:
                    files = {"file": (audio.name, f, "audio/wav")}
                    resp = await client.post(
                        url, headers=headers, data=data, files=files, timeout=self.timeout
                    )
            except Exception as exc:
                raise ProviderError(
                    redact_secrets(f"Network error: {exc}"), provider=self.name, retryable=True
                ) from exc

        if resp.status_code != 200:
            raise ProviderError(
                redact_secrets(f"OpenAI STT error HTTP {resp.status_code}: {resp.text}"),
                provider=self.name,
                retryable=resp.status_code >= 500,
            )

        resp_json = resp.json()
        segments_raw = resp_json.get("segments", [])
        if not segments_raw and resp_json.get("text"):
            # Single segment fallback
            duration = float(resp_json.get("duration", 30.0))
            return [
                RawSegment(
                    start=0.0,
                    end=duration,
                    text=resp_json["text"].strip(),
                    language=language or resp_json.get("language", "en"),
                )
            ]

        results: list[RawSegment] = []
        for s in segments_raw:
            text = s.get("text", "").strip()
            if text:
                results.append(
                    RawSegment(
                        start=float(s.get("start", 0.0)),
                        end=float(s.get("end", 0.0)),
                        text=text,
                        language=language or resp_json.get("language", "en"),
                    )
                )
        return results
