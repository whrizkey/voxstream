"""edge-tts Text-to-Speech provider with voice discovery and audio normalization."""

import asyncio
import concurrent.futures
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from voxstream.errors import ProviderError
from voxstream.providers.base import Voice

DEFAULT_VOICES_BY_LANG: dict[str, str] = {
    "en": "en-US-AriaNeural",
    "es": "es-ES-AlvaroNeural",
    "ja": "ja-JP-NanamiNeural",
    "de": "de-DE-ConradNeural",
    "fr": "fr-FR-DeniseNeural",
    "it": "it-IT-DiegoNeural",
    "pt": "pt-BR-FranciscaNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ko": "ko-KR-SunHiNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "hi": "hi-IN-SwaraNeural",
    "ar": "ar-SA-HamedNeural",
    "nl": "nl-NL-ColetteNeural",
    "pl": "pl-PL-MarekNeural",
    "tr": "tr-TR-AhmetNeural",
    "uk": "uk-UA-OstapNeural",
    "vi": "vi-VN-HoaiMyNeural",
}


class EdgeTtsProvider:
    name = "edge"
    sample_rate = 24000

    def __init__(self, default_rate: float = 1.0) -> None:
        self.default_rate = default_rate

    def _filter_voices(self, raw_voices: list[Any], lang: str) -> list[Voice]:
        results: list[Voice] = []
        target_lang = lang.lower().split("-")[0]
        for v in raw_voices:
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

        if not results:
            default_voice_id = DEFAULT_VOICES_BY_LANG.get(target_lang, "en-US-AriaNeural")
            results.append(
                Voice(
                    id=default_voice_id,
                    name=default_voice_id,
                    lang=lang,
                    gender="Neutral",
                )
            )

        return results

    async def list_voices_async(self, lang: str) -> list[Voice]:
        """Discover available Edge voices asynchronously."""
        try:
            import edge_tts

            raw_voices = await edge_tts.list_voices()
        except Exception:
            raw_voices = []

        return self._filter_voices(raw_voices, lang)

    def list_voices(self, lang: str) -> list[Voice]:
        """Discover available Edge voices for a language code (safe from running event loops)."""
        try:
            import edge_tts
        except ImportError as exc:
            raise ProviderError(
                "edge-tts is not installed. Install via `pip install edge-tts` or `uv sync --extra tts`.",
                provider=self.name,
                retryable=False,
            ) from exc

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    raw_voices = executor.submit(
                        lambda: asyncio.run(edge_tts.list_voices())
                    ).result(timeout=15.0)
            except Exception:
                raw_voices = []
        else:
            try:
                raw_voices = asyncio.run(edge_tts.list_voices())
            except Exception:
                raw_voices = []

        return self._filter_voices(raw_voices, lang)

    def _trim_and_normalize(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        # Convert stereo to mono
        if audio_data.ndim > 1:
            audio_data = np.mean(audio_data, axis=1)

        audio_data = audio_data.astype(np.float32)
        # Normalize volume to prevent clipping
        max_amp = np.max(np.abs(audio_data))
        if max_amp > 1.0:
            audio_data = audio_data / max_amp

        # Trim initial and trailing digital silence (>15ms)
        threshold = 0.005
        non_silent = np.where(np.abs(audio_data) > threshold)[0]
        if len(non_silent) > 0:
            start_idx = max(0, non_silent[0] - int(sample_rate * 0.015))
            end_idx = min(len(audio_data), non_silent[-1] + int(sample_rate * 0.015))
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
            voices = await self.list_voices_async(lang)
            target_lang = lang.lower().split("-")[0]
            default_id = DEFAULT_VOICES_BY_LANG.get(target_lang, "en-US-AriaNeural")
            selected_voice = voices[0].id if voices else default_id

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
