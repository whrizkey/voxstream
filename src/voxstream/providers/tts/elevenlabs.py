"""ElevenLabs Text-to-Speech provider."""

import tempfile
from pathlib import Path

import httpx
import soundfile as sf

from voxstream.errors import ProviderError
from voxstream.providers.base import Voice, redact_secrets


class ElevenLabsTtsProvider:
    name = "elevenlabs"
    sample_rate = 24000

    def __init__(
        self,
        api_key: str | None = None,
        model_id: str = "eleven_turbo_v2_5",
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.model_id = model_id
        self.timeout = timeout

    def list_voices(self, lang: str) -> list[Voice]:
        return [
            Voice(id="21m00Tcm4TlvDq8ikWAM", name="Rachel", lang=lang, gender="female"),
            Voice(id="AZnzlk1XvdvUeBnXmlld", name="Domi", lang=lang, gender="female"),
            Voice(id="EXAVITQu4vr4xnSDxMaL", name="Bella", lang=lang, gender="female"),
            Voice(id="ErXwobaYiN019PkySvjV", name="Antoni", lang=lang, gender="male"),
        ]

    async def synthesize(
        self,
        text: str,
        *,
        lang: str,
        voice: str | None = None,
        rate: float = 1.0,
    ) -> Path:
        if not self.api_key:
            raise ProviderError(
                "ELEVENLABS_API_KEY is not set", provider=self.name, retryable=False
            )

        voice_id = voice or "21m00Tcm4TlvDq8ikWAM"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
        }

        tmp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        mp3_path = Path(tmp_mp3.name)
        tmp_mp3.close()

        tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        wav_path = Path(tmp_wav.name)
        tmp_wav.close()

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, headers=headers, json=payload, timeout=self.timeout)
            except Exception as exc:
                if wav_path.exists():
                    wav_path.unlink(missing_ok=True)
                raise ProviderError(
                    redact_secrets(f"Network error: {exc}"), provider=self.name, retryable=True
                ) from exc

        if resp.status_code != 200:
            if wav_path.exists():
                wav_path.unlink(missing_ok=True)
            raise ProviderError(
                redact_secrets(f"ElevenLabs TTS error HTTP {resp.status_code}: {resp.text}"),
                provider=self.name,
                retryable=resp.status_code >= 500,
            )

        mp3_path.write_bytes(resp.content)
        # Decode mp3 to wav
        try:
            data, sr = sf.read(str(mp3_path))
            sf.write(str(wav_path), data, sr, format="WAV", subtype="FLOAT")
            return wav_path
        finally:
            if mp3_path.exists():
                mp3_path.unlink(missing_ok=True)
