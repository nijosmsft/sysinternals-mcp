"""Tests for pslist parser + MCP tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from sysinternals_mcp import binary_locator
from sysinternals_mcp.parsing.pslist_parser import apply_filter, parse_pslist_text
from sysinternals_mcp.tools.pslist import parse_pslist_output, pslist


@pytest.fixture(autouse=True)
def _reset() -> None:
    binary_locator.reset_cache()
    yield
    binary_locator.reset_cache()


def test_parser_loads_fixture(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "pslist.txt").read_text(encoding="utf-8")

    df = parse_pslist_text(text)

    assert not df.empty
    assert {"Name", "PID", "Pri", "Thd", "Hnd", "Priv"}.issubset(df.columns)
    assert "chrome" in df["Name"].tolist()
    assert "explorer" in df["Name"].tolist()
    assert 7892 in df["PID"].tolist()


def test_parser_skips_banner_and_blank_lines() -> None:
    text = "PsList v1.41\nCopyright ...\n\n\n"
    df = parse_pslist_text(text)
    assert df.empty


def test_apply_filter_case_insensitive_substring(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "pslist.txt").read_text(encoding="utf-8")
    df = parse_pslist_text(text)

    filtered = apply_filter(df, "CHROME")

    assert not filtered.empty
    assert (filtered["Name"] == "chrome").all()


def test_parse_pslist_output_tool(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "pslist.txt").read_text(encoding="utf-8")

    out = parse_pslist_output(text)

    assert "**Processes**" in out
    assert "chrome" in out
    assert "| Name |" in out


def test_parse_pslist_output_with_filter(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "pslist.txt").read_text(encoding="utf-8")

    out = parse_pslist_output(text, filter="chrome")

    assert "filter=`chrome`" in out
    assert "chrome" in out
    assert "explorer" not in out


def test_pslist_remote_returns_powershell_block() -> None:
    out = pslist(filter="chrome", target="remote")
    assert "```powershell" in out
    assert "pslist.exe" in out
    assert "parse_pslist_output" in out


def test_pslist_invalid_target_returns_error() -> None:
    out = pslist(target="bogus")
    assert "Unknown target" in out
