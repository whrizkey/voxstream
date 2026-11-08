"""Unit tests for the Typer CLI app."""

from typer.testing import CliRunner

from voxstream.cli import app

runner = CliRunner()


def test_cli_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "VoxStream" in result.stdout


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "doctor" in result.stdout
    assert "play" in result.stdout
    assert "process" in result.stdout


def test_cli_providers_list() -> None:
    result = runner.invoke(app, ["providers", "list"])
    assert result.exit_code == 0
    assert "faster_whisper" in result.stdout


def test_cli_doctor() -> None:
    result = runner.invoke(app, ["doctor"])
    # Should run diagnostics table
    assert "VoxStream System Diagnostics" in result.stdout
