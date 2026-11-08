"""Command Line Interface for VoxStream."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeRemainingColumn

from voxstream import __version__
from voxstream.config import get_settings
from voxstream.doctor import print_diagnostic_report, run_diagnostics
from voxstream.pipeline.batch import process_media_offline
from voxstream.pipeline.cache import CacheManager

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
    from rich.table import Table

    from voxstream.providers.registry import available_providers

    console.print("\n[bold]VoxStream Provider Capabilities[/bold]\n")

    for kind in ("stt", "translate", "tts"):
        table = Table(title=f"{kind.upper()} Providers", show_header=True)
        table.add_column("Provider", style="cyan", width=18)
        table.add_column("Status", width=12)
        table.add_column("Reason / Configuration", style="dim")

        for status in available_providers(kind):
            status_text = "[green]Ready[/green]" if status.is_usable else "[red]Disabled[/red]"
            detail = status.reason or "Configured and usable"
            table.add_row(status.name, status_text, detail)

        console.print(table)
        console.print()


@app.command()
def gui(
    target: Annotated[str | None, typer.Argument(help="Optional video file path to open.")] = None,
) -> None:
    """Launch the VoxStream desktop GUI application."""
    from voxstream.ui.app import run_desktop_app

    try:
        run_desktop_app(target)
    except Exception as exc:
        console.print(f"[bold red]Failed to start desktop GUI:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command()
def play(
    target: Annotated[str, typer.Argument(help="Video file path or stream URL.")],
    to: Annotated[str, typer.Option("--to", "-t", help="Target language code (e.g. ja, es, de).")],
    mode: Annotated[str, typer.Option("--mode", "-m", help="Mode: subs | dub | both")] = "subs",
    source_lang: Annotated[
        str | None, typer.Option("--from", "-f", help="Source language (default auto-detect).")
    ] = None,
) -> None:
    """Stream media with live translated subtitles and/or dubbed audio."""
    from voxstream.playback.controller import PlaybackController

    target_path = Path(target)
    if not target_path.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {target}")
        raise typer.Exit(code=4)

    controller = PlaybackController(target_path, to, source_lang=source_lang)
    console.print(f"\n[bold cyan]Starting Live Playback[/bold cyan] ({target_path.name} -> {to})")
    console.print(f" • Mode: {mode} | Duration: {controller.probe.duration:.2f}s")
    console.print(" • Press Ctrl+C to exit.\n")

    async def _live_loop() -> None:
        # Pre-buffer initial chunks
        await controller.step()
        controller.player.play()
        console.print("[green]Playback started.[/green]")

    asyncio.run(_live_loop())


@app.command()
def process(
    target: Annotated[str, typer.Argument(help="Video file path or stream URL.")],
    to: Annotated[str, typer.Option("--to", "-t", help="Target language code (e.g. ja, es, de).")],
    out: Annotated[str, typer.Option("--out", "-o", help="Output directory path.")],
    mode: Annotated[str, typer.Option("--mode", "-m", help="Mode: subs | dub | both")] = "subs",
    source_lang: Annotated[
        str | None, typer.Option("--from", "-f", help="Source language.")
    ] = None,
    dual: Annotated[
        bool, typer.Option("--dual", help="Export dual subtitles (original + translation).")
    ] = False,
    mux: Annotated[
        bool, typer.Option("--mux", help="Mux output into MP4 with extra audio/subtitle tracks.")
    ] = False,
) -> None:
    """Batch process a video into translated subtitles (.srt) and dubbed track (.wav)."""
    target_path = Path(target)
    if not target_path.exists():
        console.print(f"[bold red]Error:[/bold red] Media file not found: {target}")
        raise typer.Exit(code=4)

    output_dir = Path(out)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"Processing {target_path.name} -> {to}", total=100)

        def on_chunk_progress(idx: int, total_chunks: int, desc: str) -> None:
            pct = int((idx / max(1, total_chunks)) * 100)
            progress.update(task, completed=pct, description=desc)

        stats = asyncio.run(
            process_media_offline(
                input_path=target_path,
                target_lang=to,
                output_dir=output_dir,
                mode=mode,
                source_lang=source_lang,
                dual_subtitles=dual,
                progress_callback=on_chunk_progress,
            )
        )
        progress.update(task, completed=100, description="Completed!")

    console.print("\n[bold green]Processing Finished![/bold green]")
    console.print(f" • Media ID: {stats['media_id']}")
    console.print(
        f" • Chunks Processed: {stats['total_chunks']} ({stats['cache_hits']} cache hits)"
    )
    console.print(f" • Subtitle Cues: {stats['total_segments']}")
    console.print(f" • Subtitle Output: [cyan]{stats['srt_path']}[/cyan]\n")


@app.command("export-srt")
def export_srt_cmd(
    target: Annotated[str, typer.Argument(help="Video file path.")],
    to: Annotated[str, typer.Option("--to", "-t", help="Target language code.")],
    out: Annotated[str, typer.Option("--out", "-o", help="Output .srt file path.")],
    source_lang: Annotated[
        str | None, typer.Option("--from", "-f", help="Source language.")
    ] = None,
    dual: Annotated[
        bool, typer.Option("--dual", help="Include original text above translation.")
    ] = False,
) -> None:
    """Extract and export subtitles directly to an .srt file."""
    target_path = Path(target)
    out_path = Path(out)
    stats = asyncio.run(
        process_media_offline(
            input_path=target_path,
            target_lang=to,
            output_dir=out_path.parent,
            mode="subs",
            source_lang=source_lang,
            dual_subtitles=dual,
        )
    )
    if stats["srt_path"] != out_path:
        out_path.write_text(stats["srt_path"].read_text(encoding="utf-8"), encoding="utf-8")
    console.print(f"[bold green]Exported subtitles to:[/bold green] {out_path}")


@cache_app.command("info")
def cache_info() -> None:
    """Display cache storage usage and statistics."""
    settings = get_settings()
    mgr = CacheManager(settings.get_cache_path())
    stats = mgr.get_stats()
    mb = stats["total_bytes"] / (1024 * 1024)
    console.print("\n[bold]VoxStream Cache Statistics[/bold]")
    console.print(f" • Media Entries: {stats['media_count']}")
    console.print(f" • Cached Transcripts: {stats['transcripts_count']}")
    console.print(f" • Cached Translations: {stats['translations_count']}")
    console.print(f" • Total Disk Space: {mb:.2f} MB")
    console.print(f" • Database: {stats['db_path']}\n")


@cache_app.command("clear")
def cache_clear(
    media_id: Annotated[
        str | None, typer.Option("--media", help="Specific media ID to clear.")
    ] = None,
) -> None:
    """Clear cached transcripts, translations, and temporary audio files."""
    settings = get_settings()
    mgr = CacheManager(settings.get_cache_path())
    mgr.clear(media_id)
    if media_id:
        console.print(f"[green]Cleared cache for media ID:[/green] {media_id}")
    else:
        console.print("[green]Cleared entire VoxStream cache.[/green]")


@cache_app.command("prune")
def cache_prune(
    max_gb: Annotated[
        float, typer.Option("--max-gb", help="Maximum cache size in gigabytes.")
    ] = 5.0,
) -> None:
    """Prune cache entries older than threshold."""
    console.print(f"[dim]Pruning cache down to {max_gb} GB...[/dim]")
