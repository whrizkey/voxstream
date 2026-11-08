"""Unit tests for the doctor diagnostics tool."""

from voxstream.doctor import (
    CheckResult,
    DiagnosticReport,
    check_binary,
    print_diagnostic_report,
    run_diagnostics,
)


def test_check_binary_not_found() -> None:
    result = check_binary("non_existent_binary_xyz_123")
    assert result.status is False
    assert result.is_critical is True
    assert "not found" in result.detail.lower()


def test_diagnostic_report_critical_failure_flag() -> None:
    ok_check = CheckResult(name="TestOK", status=True, detail="All good", is_critical=True)
    warn_check = CheckResult(
        name="TestWarn", status=False, detail="Optional issue", is_critical=False
    )
    crit_check = CheckResult(name="TestCrit", status=False, detail="Fatal error", is_critical=True)

    report_healthy = DiagnosticReport(checks=[ok_check, warn_check])
    assert report_healthy.has_critical_failures is False
    assert print_diagnostic_report(report_healthy) == 0

    report_broken = DiagnosticReport(checks=[ok_check, crit_check])
    assert report_broken.has_critical_failures is True
    assert print_diagnostic_report(report_broken) == 1


def test_run_diagnostics_executes_without_exceptions() -> None:
    report = run_diagnostics()
    assert len(report.checks) > 0
    names = [c.name for c in report.checks]
    assert "Python" in names
    assert "ffmpeg" in names
