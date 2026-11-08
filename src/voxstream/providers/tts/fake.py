"""Fake deterministic TTS provider for offline testing."""

import math
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from voxstream.providers.base import Voice


class FakeTtsProvider:
    name = "fake"
    sample_rate = 24000

    def list_voices(self, lang: str) -> list[Voice]:
        return [
            Voice(
                id=f"fake-{lang}-neutral",
                name=f"Fake {lang.upper()} Neutral",
                lang=lang,
                gender="neutral",
            )
        ]

    async def synthesize(
        self,
        text: str,
        *,
        lang: str,
        voice: str | None = None,
        rate: float = 1.0,
    ) -> Path:
        # Approximate speech duration: ~14 characters per second, scaled by rate
        char_count = max(1, len(text.strip()))
        duration = max(0.4, (char_count / 14.0) / max(0.2, rate))

        num_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, num_samples, endpoint=False)

        # Generate a gentle 440Hz sine wave with 20ms fade in/out
        frequency = 440.0
        audio = 0.2 * np.sin(2 * math.pi * frequency * t).astype(np.float32)

        fade_samples = min(int(self.sample_rate * 0.02), num_samples // 4)
        if fade_samples > 0:
            fade_in = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
            fade_out = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
            audio[:fade_samples] *= fade_in
            audio[-fade_samples:] *= fade_out

        tmp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = Path(tmp_file.name)
        tmp_file.close()

        sf.write(tmp_path, audio, self.sample_rate, format="WAV", subtype="FLOAT")
        return tmp_path
