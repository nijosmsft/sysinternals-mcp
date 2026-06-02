"""Tests for tcpvcon parser + MCP tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from sysinternals_mcp import binary_locator
from sysinternals_mcp.parsing.tcpvcon_parser import parse_tcpvcon_csv
from sysinternals_mcp.tools.tcpvcon import parse_tcpvcon_output, tcpvcon


@pytest.fixture(autouse=True)
def _reset() -> None:
    binary_locator.reset_cache()
    yield
    binary_locator.reset_cache()


def test_parser_loads_csv(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "tcpvcon.csv").read_text(encoding="utf-8")

    df = parse_tcpvcon_csv(text)

    assert not df.empty
    assert {
        "Protocol",
        "Process",
        "PID",
        "State",
        "LocalAddr",
        "LocalPort",
        "RemoteAddr",
        "RemotePort",
    } <= set(df.columns)
    assert (df["Protocol"] == "TCP").any()
    assert (df["Protocol"] == "UDP").any()
    assert (df["Process"] == "chrome.exe").sum() == 2


def test_parser_returns_empty_for_blank_input() -> None:
    df = parse_tcpvcon_csv("")
    assert df.empty


def test_parser_skips_banner_lines() -> None:
    text = (
        "TCPView v4.19\n"
        "Copyright (C) Mark Russinovich\n"
        "TCP,system,4,LISTENING,0.0.0.0,445,0.0.0.0,0\n"
    )
    df = parse_tcpvcon_csv(text)
    assert len(df) == 1


def test_parse_tcpvcon_output_tool(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "tcpvcon.csv").read_text(encoding="utf-8")

    out = parse_tcpvcon_output(text)

    assert "**tcpvcon endpoints**" in out
    assert "chrome.exe" in out
    assert "TCP" in out


def test_parse_tcpvcon_output_with_filter(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "tcpvcon.csv").read_text(encoding="utf-8")

    out = parse_tcpvcon_output(text, filter="chrome")

    assert "chrome.exe" in out
    assert "explorer.exe" not in out
    assert "svchost.exe" not in out


def test_parse_tcpvcon_output_handles_empty() -> None:
    out = parse_tcpvcon_output("")
    assert "Empty input" in out


def test_tcpvcon_remote_emits_lablink_first_block() -> None:
    out = tcpvcon(target="remote")

    assert "**Recommended dispatch:** LabLink" in out
    assert "```powershell" in out
    assert "```json" in out
    assert "tcpvcon.exe" in out
    assert "-a" in out
    assert "-c" in out
    assert "-n" in out
    assert '"parse_with": "parse_tcpvcon_output"' in out


def test_tcpvcon_rejects_unknown_target() -> None:
    out = tcpvcon(target="cluster")
    assert "Unknown target" in out


def test_tcpvcon_filter_applies_to_remote_note() -> None:
    out = tcpvcon(target="remote", filter="chrome")
    assert "chrome" in out
