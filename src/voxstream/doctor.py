"""System diagnostics and environment inspection."""

import ctypes.util
import shutil
import subprocess
import sys
from dataclasses import dataclass

from rich.console import Console
from rich.table import Table

from voxstream.config import get_settings


@dataclass
class CheckResult:
    name: str
    status: bool  # True = ok, False = fail
    detail: str
    action_item: str | None = None
    is_critical: bool = True


@dataclass
class DiagnosticReport:
    checks: list[CheckResult]

    @property
    def has_critical_failures(self) -> bool:
        return any(not c.status and c.is_critical for c in self.checks)


def check_binary(name: str, min_version_flag: str = "-version") -> CheckResult:
    path = shutil.which(name)
    if not path:
        return CheckResult(
            name=name,
            status=False,
            detail="Binary not found on system PATH",
            action_item=f"Install {name} using your package manager (e.g. apt/brew install {name})",
            is_critical=True,
        )
    try:
        proc = subprocess.run([name, min_version_flag], capture_output=True, text=True, timeout=3)
        first_line = proc.stdout.splitlines()[0] if proc.stdout else "found"
        return CheckResult(name=name, status=True, detail=f"{path} ({first_line})")
    except Exception as e:
        return CheckResult(
            name=name,
            status=False,
            detail=f"Error executing {name}: {e}",
            action_item=f"Ensure {name} has executable permissions and is compatible with your architecture",
            is_critical=True,
        )


def check_libmpv() -> CheckResult:
    # Check via python module first if installed
    import importlib.util

    if importlib.util.find_spec("mpv") is not None:
        return CheckResult(name="libmpv", status=True, detail="Found python-mpv package")

    # Check via system library search
    lib = ctypes.util.find_library("mpv")
    if lib:
        return CheckResult(name="libmpv", status=True, detail=f"Found system library: {lib}")

    return CheckResult(
        name="libmpv",
        status=False,
        detail="libmpv dynamic library not found",
        action_item="Install libmpv (Ubuntu/Debian: apt install libmpv2 or libmpv-dev, macOS: brew install mpv)",
        is_critical=False,  # CLI process mode can still work without mpv
    )


def check_audio_devices() -> CheckResult:
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        default_out = sd.default.device[1]
        out_name = (
            devices[default_out]["name"] if default_out is not None and default_out >= 0 else "None"
        )
        return CheckResult(
            name="Audio Output",
            status=True,
            detail=f"Default device: {out_name}",
        )
    except Exception as e:
        return CheckResult(
            name="Audio Output",
            status=False,
            detail=f"Failed to query audio devices: {e}",
            action_item="Ensure PortAudio / sounddevice is functional and an audio output device is connected",
            is_critical=False,
        )


def check_gpu() -> CheckResult:
    has_nvidia = shutil.which("nvidia-smi") is not None
    try:
        import torch

        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            return CheckResult(name="GPU Acceleration", status=True, detail=f"CUDA: {device_name}")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return CheckResult(name="GPU Acceleration", status=True, detail="Apple Metal (MPS)")
    except Exception:
        pass

    if has_nvidia:
        return CheckResult(
            name="GPU Acceleration",
            status=True,
            detail="NVIDIA GPU detected via nvidia-smi (Torch not yet installed)",
        )

    return CheckResult(
        name="GPU Acceleration",
        status=True,
        detail="CPU only (GPU acceleration optional for local Whisper)",
        is_critical=False,
    )


def check_providers() -> CheckResult:
    settings = get_settings()
    usable: list[str] = ["fake"]

    # Check faster-whisper
    try:
        import faster_whisper  # noqa: F401

        usable.append("faster_whisper")
    except ImportError:
        pass

    # Check edge-tts
    try:
        import edge_tts  # noqa: F401

        usable.append("edge")
    except ImportError:
        pass

    # Check API keys
    if settings.openai_key_str:
        usable.append("openai_compat")
    if settings.anthropic_key_str:
        usable.append("anthropic")
    if settings.deepl_key_str:
        usable.append("deepl")
    if settings.elevenlabs_key_str:
        usable.append("elevenlabs")

    return CheckResult(
        name="Providers",
        status=True,
        detail=f"Active STT: {settings.stt_provider}, Translate: {settings.translate_provider}, TTS: {settings.tts_provider} | Available: {', '.join(usable)}",
        is_critical=False,
    )


def run_diagnostics() -> DiagnosticReport:
    """Execute all diagnostic checks and assemble a report."""
    checks = [
        CheckResult(
            name="Python", status=True, detail=f"{sys.version.split()[0]} ({sys.executable})"
        ),
        check_binary("ffmpeg"),
        check_binary("ffprobe"),
        check_libmpv(),
        check_audio_devices(),
        check_gpu(),
        check_providers(),
    ]
    return DiagnosticReport(checks=checks)


def print_diagnostic_report(report: DiagnosticReport) -> int:
    """Print formatted diagnostic results and return exit code (0 = ok, 1 = failure)."""
    console = Console()
    console.print("\n[bold]VoxStream System Diagnostics[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan", width=20)
    table.add_column("Status", width=10)
    table.add_column("Details", style="dim")

    for check in report.checks:
        status_text = (
            "[green]OK[/green]"
            if check.status
            else ("[red]FAIL[/red]" if check.is_critical else "[yellow]WARN[/yellow]")
        )
        table.add_row(check.name, status_text, check.detail)

    console.print(table)

    failures = [c for c in report.checks if not c.status]
    if failures:
        console.print("\n[bold yellow]Remediation Recommendations:[/bold yellow]")
        for f in failures:
            if f.action_item:
                console.print(f" • [bold]{f.name}[/bold]: {f.action_item}")

    console.print()
    return 1 if report.has_critical_failures else 0
