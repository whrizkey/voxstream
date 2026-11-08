"""faster-whisper STT provider implementation."""

import asyncio
from pathlib import Path
from typing import Any

from voxstream.errors import ProviderError
from voxstream.providers.base import RawSegment


class FasterWhisperSttProvider:
    name = "faster_whisper"

    def __init__(
        self, model_size: str = "small", device: str = "auto", compute_type: str = "auto"
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: Any = None

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ProviderError(
                "faster-whisper is not installed. Install via `pip install faster-whisper` or `uv sync --extra local-stt`.",
                provider=self.name,
                retryable=False,
            ) from exc

        # Auto-detect device and quantization
        chosen_device = self.device
        chosen_compute = self.compute_type

        if chosen_device == "auto":
            try:
                import torch

                chosen_device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                chosen_device = "cpu"

        if chosen_compute == "auto":
            chosen_compute = "float16" if chosen_device == "cuda" else "int8"

        try:
            self._model = WhisperModel(
                self.model_size, device=chosen_device, compute_type=chosen_compute
            )
            return self._model
        except Exception as exc:
            raise ProviderError(
                f"Failed to load WhisperModel({self.model_size}): {exc}",
                provider=self.name,
                retryable=False,
            ) from exc

    def _transcribe_sync(
        self,
        audio_path: Path,
        language: str | None,
        word_timestamps: bool,
    ) -> list[RawSegment]:
        model = self._ensure_model()
        try:
            segments, info = model.transcribe(
                str(audio_path),
                language=language,
                word_timestamps=word_timestamps,
                vad_filter=True,
            )
            detected_lang = language or info.language
            results: list[RawSegment] = []
            for s in segments:
                text = s.text.strip()
                if not text:
                    continue
                results.append(
                    RawSegment(
                        start=float(s.start),
                        end=float(s.end),
                        text=text,
                        language=detected_lang,
                        confidence=float(getattr(s, "avg_logprob", 0.0)),
                    )
                )
            return results
        except Exception as exc:
            raise ProviderError(
                f"Transcription error: {exc}",
                provider=self.name,
                retryable=False,
            ) from exc

    async def transcribe(
        self,
        audio: Path,
        *,
        language: str | None = None,
        word_timestamps: bool = False,
    ) -> list[RawSegment]:
        return await asyncio.to_thread(self._transcribe_sync, audio, language, word_timestamps)
