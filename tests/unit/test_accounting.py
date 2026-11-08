import pytest
from rich.console import Console

from voxstream.errors import BudgetExceededError
from voxstream.providers.accounting import UsageTracker


def test_usage_tracker_accumulation_and_cost() -> None:
    tracker = UsageTracker()

    # 120 seconds of STT
    tracker.record_stt("openai_compat_stt", 120.0)
    # 2000 characters of translation
    tracker.record_translation("anthropic", 2000)
    # 1000 characters of ElevenLabs TTS
    tracker.record_tts("elevenlabs", 1000)

    cost = tracker.estimate_cost_usd()
    # 120s STT = 2 min * $0.006 = $0.012
    # 2000 chars Anthropic = 2 * $0.001 = $0.002
    # 1000 chars ElevenLabs = 1 * $0.15 = $0.15
    # Total = 0.012 + 0.002 + 0.15 = $0.164
    assert abs(cost - 0.164) < 1e-4

    console = Console(record=True)
    tracker.print_summary(console)
    output = console.export_text()
    assert "Session Provider Usage" in output
    assert "TOTAL" in output


def test_usage_tracker_budget_ceiling() -> None:
    tracker = UsageTracker(max_cost_usd=0.01)
    tracker.record_stt("openai_compat_stt", 60.0)

    with pytest.raises(BudgetExceededError) as exc_info:
        tracker.record_stt("openai_compat_stt", 60.0)
    assert "Cost ceiling exceeded" in str(exc_info.value)
