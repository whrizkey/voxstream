import tomllib
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table


@dataclass
class UsageItem:
    provider: str
    kind: str  # "stt", "translate", "tts"
    quantity: float
    unit: str  # "seconds", "characters", "tokens"


# Default estimated pricing table (USD per unit)
DEFAULT_RATES: dict[str, float] = {
    # STT: per second
    "openai_compat_stt": 0.006 / 60.0,
    "faster_whisper": 0.0,
    # Translation: per 1,000 characters
    "openai_compat": 0.0006 / 1000.0,
    "anthropic": 0.001 / 1000.0,
    "deepl": 0.02 / 1000.0,
    # TTS: per 1,000 characters
    "edge": 0.0,
    "openai_tts": 0.015 / 1000.0,
    "elevenlabs": 0.15 / 1000.0,
    "piper": 0.0,
    "fake": 0.0,
}


def load_pricing_rates(custom_file: Path | None = None) -> dict[str, float]:
    """Load rates from pricing.toml if present, falling back to DEFAULT_RATES."""
    rates = dict(DEFAULT_RATES)
    candidates = [
        custom_file,
        Path("pricing.toml"),
        Path.home() / ".config" / "voxstream" / "pricing.toml",
    ]
    for p in candidates:
        if p and p.is_file():
            try:
                data = tomllib.loads(p.read_text(encoding="utf-8"))
                pricing_section = data.get("pricing", {})
                if isinstance(pricing_section, dict):
                    for k, v in pricing_section.items():
                        if isinstance(v, (int, float)):
                            rates[str(k)] = float(v)
                break
            except Exception:
                pass
    return rates


class UsageTracker:
    """Accumulates provider usage across a processing session and estimates cost."""

    def __init__(self, rates: dict[str, float] | None = None) -> None:
        self.records: list[UsageItem] = []
        self.rates = rates if rates is not None else load_pricing_rates()

    def record_stt(self, provider: str, audio_seconds: float) -> None:
        self.records.append(
            UsageItem(provider=provider, kind="stt", quantity=audio_seconds, unit="seconds")
        )

    def record_translation(self, provider: str, char_count: int) -> None:
        self.records.append(
            UsageItem(
                provider=provider, kind="translate", quantity=float(char_count), unit="characters"
            )
        )

    def record_tts(self, provider: str, char_count: int) -> None:
        self.records.append(
            UsageItem(provider=provider, kind="tts", quantity=float(char_count), unit="characters")
        )

    def estimate_cost_usd(self) -> float:
        total = 0.0
        for r in self.records:
            rate = self.rates.get(r.provider, 0.0)
            total += r.quantity * rate
        return total

    def print_summary(self, console: Console) -> None:
        if not self.records:
            return

        table = Table(title="Session Provider Usage & Estimated Costs", show_header=True)
        table.add_column("Stage", style="cyan")
        table.add_column("Provider", style="magenta")
        table.add_column("Quantity", justify="right")
        table.add_column("Est. Cost (USD)", justify="right", style="green")

        total_cost = 0.0
        for r in self.records:
            rate = self.rates.get(r.provider, 0.0)
            cost = r.quantity * rate
            total_cost += cost
            table.add_row(
                r.kind.upper(),
                r.provider,
                f"{r.quantity:,.0f} {r.unit}",
                f"${cost:.4f}" if cost > 0.0001 else "Free / Local",
            )

        table.add_section()
        table.add_row("TOTAL", "", "", f"${total_cost:.4f}")
        console.print(table)
