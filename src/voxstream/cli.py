"""Command Line Interface for VoxStream."""

from typing import Annotated

import typer
from rich.console import Console

from voxstream import __version__
from voxstream.doctor import print_diagnostic_report, run_diagnostics

app = typer.Typer(
    name="voxstream",
    help="Real-time speech translation and dubbing player that buffers ahead of the playhead.",
    no_args_is_help=True,
)
console = Console()

providers_app = typer.Typer(help="Inspect and configure speech and language providers.")
cache_app = typer.Typer(help="Manage local transcription and audio cache.")

app.add_typer(providers_app, name="providers")
app.add_typer(cache_app, name="cache")


def version_callback(value: bool) -> None:
    if value:
        console.print(
            f"[bold cyan]VoxStream[/bold cyan] version [bold green]{__version__}[/bold green]"
        )
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
) -> None:
    """VoxStream: Live video subtitle and dubbing engine."""


@app.command()
def doctor() -> None:
    """Inspect local system environment, binaries (ffmpeg, mpv), and provider readiness."""
    report = run_diagnostics()
    exit_code = print_diagnostic_report(report)
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@providers_app.command("list")
def list_providers() -> None:
    """List available and active STT, translation, and TTS providers."""
    console.print("\n[bold]Configured Providers[/bold]")
    console.print(" • STT: faster_whisper, openai_compat, fake")
    console.print(" • Translation: openai_compat, anthropic, deepl, fake")
    console.print(" • TTS: edge, openai, elevenlabs, piper, fake\n")


@app.command()
def play(
    target: Annotated[str, typer.Argument(help="Video file path or stream URL.")],
    to: Annotated[str, typer.Option("--to", "-t", help="Target language code (e.g. ja, es, de).")],
    mode: Annotated[str, typer.Option("--mode", "-m", help="Mode: subs | dub | both")] = "both",
    source_lang: Annotated[
        str | None, typer.Option("--from", "-f", help="Source language (default auto-detect).")
    ] = None,
) -> None:
    """Stream media with live translated subtitles and/or dubbed audio."""
    console.print("[bold yellow]Live player queued for Milestone 4 & 5.[/bold yellow]")
    console.print(f"Target: {target} | Target Language: {to} | Mode: {mode}")


@app.command()
def process(
    target: Annotated[str, typer.Argument(help="Video file path or stream URL.")],
    to: Annotated[str, typer.Option("--to", "-t", help="Target language code (e.g. ja, es, de).")],
    out: Annotated[str, typer.Option("--out", "-o", help="Output directory path.")],
    mode: Annotated[str, typer.Option("--mode", "-m", help="Mode: subs | dub | both")] = "both",
    mux: Annotated[
        bool, typer.Option("--mux", help="Mux output into MP4 with extra audio/subtitle tracks.")
    ] = False,
) -> None:
    """Batch process a video into translated subtitles (.srt) and dubbed track (.wav)."""
    console.print("[bold yellow]Batch processor queued for Milestone 2 & 3.[/bold yellow]")
    console.print(f"Target: {target} | Target Language: {to} | Output: {out} | Mux: {mux}")


@cache_app.command("info")
def cache_info() -> None:
    """Display cache storage usage and statistics."""
    console.print("[dim]Cache stats: 0 entries (pipeline bootstrap)[/dim]")


@cache_app.command("prune")
def cache_prune(
    max_gb: Annotated[
        float, typer.Option("--max-gb", help="Maximum cache size in gigabytes.")
    ] = 5.0,
) -> None:
    """Prune cache entries older than threshold."""
    console.print(f"[dim]Pruning cache down to {max_gb} GB... Cleaned 0 bytes.[/dim]")
