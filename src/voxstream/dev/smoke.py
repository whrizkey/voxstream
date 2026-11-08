"""Smoke test script executing STT -> Translate -> TTS end-to-end."""

import asyncio
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from rich.console import Console

from voxstream.providers.base import TranslateItem
from voxstream.providers.registry import (
    check_provider_usable,
    get_stt_provider,
    get_translate_provider,
    get_tts_provider,
)

console = Console()


def generate_sample_clip(duration: float = 10.0, sample_rate: int = 16000) -> Path:
    """Generate a clean synthetic audio WAV file for testing."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    num_samples = int(duration * sample_rate)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    # A simple modulated tone simulating speech presence
    audio = (0.2 * np.sin(2 * math.pi * 300 * t) * (np.sin(2 * math.pi * 2 * t) > 0)).astype(
        np.float32
    )

    sf.write(str(tmp_path), audio, sample_rate)
    return tmp_path


async def run_smoke_test(target_lang: str = "es") -> int:
    console.print("\n[bold cyan]VoxStream Pipeline Smoke Test[/bold cyan]\n")

    # Determine providers (real vs fake based on readiness)
    stt_status = check_provider_usable("stt", "faster_whisper")
    trans_status = check_provider_usable("translate", "openai_compat")
    tts_status = check_provider_usable("tts", "edge")

    stt_name = "faster_whisper" if stt_status.is_usable else "fake"
    trans_name = "openai_compat" if trans_status.is_usable else "fake"
    tts_name = "edge" if tts_status.is_usable else "fake"

    console.print(f" • STT Provider: [bold]{stt_name}[/bold] (Real ready: {stt_status.is_usable})")
    console.print(
        f" • Translate Provider: [bold]{trans_name}[/bold] (Real ready: {trans_status.is_usable})"
    )
    console.print(
        f" • TTS Provider: [bold]{tts_name}[/bold] (Real ready: {tts_status.is_usable})\n"
    )

    clip_path = generate_sample_clip(duration=10.0)
    try:
        # 1. Transcribe
        console.print("[dim]1. Running STT transcription...[/dim]")
        stt = get_stt_provider(stt_name)
        segments = await stt.transcribe(clip_path)
        console.print(f"   [green]OK[/green] Produced {len(segments)} segments:")
        for seg in segments:
            console.print(f"    - [{seg.start:.2f}s - {seg.end:.2f}s] {seg.text}")

        # 2. Translate
        console.print("\n[dim]2. Running Translation...[/dim]")
        trans = get_translate_provider(trans_name)
        items = [
            TranslateItem(id=f"seg_{i}", text=seg.text, duration=seg.end - seg.start)
            for i, seg in enumerate(segments)
        ]
        translated = await trans.translate(
            items, source_lang="en", target_lang=target_lang, context=[]
        )
        console.print(
            f"   [green]OK[/green] Translated {len(translated)} segments to {target_lang}:"
        )
        for t in translated:
            console.print(f"    - [{t.id}] {t.text}")

        # 3. TTS Synthesis
        console.print("\n[dim]3. Running TTS Synthesis...[/dim]")
        tts = get_tts_provider(tts_name)
        for t in translated:
            wav_path = await tts.synthesize(t.text, lang=target_lang)
            data, sr = sf.read(str(wav_path))
            dur = len(data) / sr
            console.print(
                f"   [green]OK[/green] Synthesized '{t.id}': {dur:.2f}s audio at {sr}Hz ({wav_path.name})"
            )
            if wav_path.exists():
                wav_path.unlink(missing_ok=True)

        console.print("\n[bold green]Smoke test completed successfully![/bold green]\n")
        return 0
    except Exception as exc:
        console.print(f"\n[bold red]Smoke test failed:[/bold red] {exc}\n")
        return 1
    finally:
        if clip_path.exists():
            clip_path.unlink(missing_ok=True)


if __name__ == "__main__":
    code = asyncio.run(run_smoke_test())
    sys.exit(code)
