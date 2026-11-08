"""Vocal and background music (BGM) separation using Demucs or fake backends."""

import asyncio
import shutil
import wave
from pathlib import Path
from typing import Protocol

from voxstream.errors import ExternalToolError


class AudioSeparator(Protocol):
    """Protocol for audio source separation (vocals vs accompaniment/BGM)."""

    name: str

    async def separate(self, audio_path: Path, output_dir: Path) -> tuple[Path, Path]:
        """Separate audio into (vocals_path, bgm_path)."""
        ...


class FakeSeparator:
    """Offline test separator producing valid silent or tone WAV files."""

    name: str = "fake_separator"

    async def separate(self, audio_path: Path, output_dir: Path) -> tuple[Path, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        vocals = output_dir / f"{audio_path.stem}_vocals.wav"
        bgm = output_dir / f"{audio_path.stem}_bgm.wav"

        # Create minimal 16-bit 16kHz mono WAV files
        for p in (vocals, bgm):
            with wave.open(str(p), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00" * 32000)  # 1 second of silence

        return vocals, bgm


class DemucsSeparator:
    """Audio source separation using Demucs (htdemucs).

    Extracts vocals and accompaniment (drums + bass + other) stems.
    Requires `demucs` CLI installed in PATH or environment.
    """

    name: str = "demucs"

    def __init__(self, model: str = "htdemucs") -> None:
        self.model = model

    async def separate(self, audio_path: Path, output_dir: Path) -> tuple[Path, Path]:
        demucs_bin = shutil.which("demucs")
        if not demucs_bin:
            raise ExternalToolError(
                "Demucs CLI not found on PATH. Install with `pip install demucs` or run `uv pip install demucs`."
            )

        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            demucs_bin,
            "-n",
            self.model,
            "--two-stems",
            "vocals",
            "-o",
            str(output_dir),
            str(audio_path),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise ExternalToolError(
                f"Demucs separation failed with exit code {proc.returncode}: {stderr.decode(errors='replace')}"
            )

        # Demucs output structure: output_dir / model / stem_name / (vocals.wav, no_vocals.wav)
        model_out = output_dir / self.model / audio_path.stem
        vocals = model_out / "vocals.wav"
        bgm = model_out / "no_vocals.wav"

        if not vocals.exists() or not bgm.exists():
            raise ExternalToolError(
                f"Demucs output stems not found in expected directory: {model_out}"
            )

        return vocals, bgm
