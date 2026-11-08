"""edge-tts Text-to-Speech provider with voice discovery and audio normalization."""

import asyncio
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from voxstream.errors import ProviderError
from voxstream.providers.base import Voice


class EdgeTtsProvider:
    name = "edge"
    sample_rate = 24000

    def __init__(self, default_rate: float = 1.0) -> None:
        self.default_rate = default_rate

    def list_voices(self, lang: str) -> list[Voice]:
        """Discover available Edge voices for a language code."""
        try:
            import edge_tts
        except ImportError as exc:
            raise ProviderError(
                "edge-tts is not installed. Install via `pip install edge-tts` or `uv sync --extra tts`.",
                provider=self.name,
                retryable=False,
            ) from exc

        # Synchronous voice listing wrapper
        try:
            voices = asyncio.run(edge_tts.list_voices())
        except Exception:
            voices = []

        results: list[Voice] = []
        target_lang = lang.lower().split("-")[0]
        for v in voices:
            locale = v.get("Locale", "").lower()
            if locale.startswith(target_lang) or locale.split("-")[0] == target_lang:
                results.append(
                    Voice(
                        id=v.get("ShortName", ""),
                        name=v.get("FriendlyName", v.get("ShortName", "")),
                        lang=v.get("Locale", lang),
                        gender=v.get("Gender"),
                    )
                )
        return results

    def _trim_and_normalize(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        # Convert stereo to mono
        if audio_data.ndim > 1:
            audio_data = np.mean(audio_data, axis=1)

        audio_data = audio_data.astype(np.float32)
        # Normalize volume to prevent clipping
        max_amp = np.max(np.abs(audio_data))
        if max_amp > 0.001:
            audio_data = audio_data / max_amp * 0.95

        # Trim leading/trailing silence (> 80ms)
        threshold = 0.01
        is_sound = np.abs(audio_data) > threshold
        if np.any(is_sound):
            indices = np.where(is_sound)[0]
            start_idx = max(0, indices[0] - int(sample_rate * 0.02))
            end_idx = min(len(audio_data), indices[-1] + int(sample_rate * 0.02))
            audio_data = audio_data[start_idx:end_idx]

        return audio_data

    async def synthesize(
        self,
        text: str,
        *,
        lang: str,
        voice: str | None = None,
        rate: float = 1.0,
    ) -> Path:
        try:
            import edge_tts
        except ImportError as exc:
            raise ProviderError(
                "edge-tts is not installed. Install via `pip install edge-tts`.",
                provider=self.name,
                retryable=False,
            ) from exc

        clean_text = text.strip()
        if not clean_text:
            raise ProviderError("Cannot synthesize empty text", provider=self.name, retryable=False)

        # Select appropriate voice if not specified
        selected_voice = voice
        if not selected_voice:
            voices = self.list_voices(lang)
            selected_voice = voices[0].id if voices else "en-US-AriaNeural"

        # Calculate rate adjustment string e.g. "+10%", "-5%"
        rate_diff = round((rate - 1.0) * 100)
        rate_str = f"{rate_diff:+d}%"

        tmp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_mp3_path = Path(tmp_mp3.name)
        tmp_mp3.close()

        output_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_wav_path = Path(output_wav.name)
        output_wav.close()

        try:
            communicate = edge_tts.Communicate(clean_text, selected_voice, rate=rate_str)
            await communicate.save(str(tmp_mp3_path))

            # Decode and normalize
            data, sr = sf.read(str(tmp_mp3_path))
            normalized = self._trim_and_normalize(data, sr)
            sf.write(str(output_wav_path), normalized, sr, format="WAV", subtype="FLOAT")
            return output_wav_path
        except Exception as exc:
            if output_wav_path.exists():
                output_wav_path.unlink(missing_ok=True)
            raise ProviderError(
                f"TTS synthesis failed: {exc}", provider=self.name, retryable=True
            ) from exc
        finally:
            if tmp_mp3_path.exists():
                tmp_mp3_path.unlink(missing_ok=True)
