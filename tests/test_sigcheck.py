"""Tests for sigcheck parser + MCP tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from sysinternals_mcp import binary_locator
from sysinternals_mcp.parsing.sigcheck_parser import parse_sigcheck_csv
from sysinternals_mcp.tools.sigcheck import parse_sigcheck_output, sigcheck


@pytest.fixture(autouse=True)
def _reset() -> None:
    binary_locator.reset_cache()
    yield
    binary_locator.reset_cache()


def test_parser_loads_csv(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "sigcheck.csv").read_text(encoding="utf-8")

    df = parse_sigcheck_csv(text)

    assert not df.empty
    assert "Path" in df.columns
    assert "Verified" in df.columns
    assert "SHA256" in df.columns
    assert any("notepad.exe" in p for p in df["Path"])


def test_parser_handles_bom() -> None:
    text = '\ufeff"Path","Verified"\n"foo.exe","Signed"\n'
    df = parse_sigcheck_csv(text)
    assert len(df) == 1
    assert df["Path"][0] == "foo.exe"


def test_parser_returns_empty_for_blank_input() -> None:
    df = parse_sigcheck_csv("")
    assert df.empty


def test_parse_sigcheck_output_tool(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "sigcheck.csv").read_text(encoding="utf-8")

    out = parse_sigcheck_output(text)

    assert "**Sigcheck" in out
    assert "notepad.exe" in out
    assert "SHA256" in out


def test_parse_sigcheck_output_handles_empty() -> None:
    out = parse_sigcheck_output("")
    assert "Empty input" in out


def test_sigcheck_remote_emits_command_block() -> None:
    out = sigcheck(path=r"C:\Windows\System32\notepad.exe", target="remote")

    assert "```powershell" in out
    assert "sigcheck.exe" in out
    assert "-c" in out
    assert "-a" in out
    assert "-h" in out
    assert "parse_sigcheck_output" in out


def test_sigcheck_rejects_unknown_target() -> None:
    out = sigcheck(path=r"C:\Windows\notepad.exe", target="cluster")
    assert "Unknown target" in out


def test_sigcheck_empty_path_returns_error() -> None:
    out = sigcheck(path="", target="local")
    assert "non-empty" in out
