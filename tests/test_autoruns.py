"""Tests for autoruns parser + MCP tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from sysinternals_mcp import binary_locator
from sysinternals_mcp.parsing.autorunsc_parser import parse_autorunsc_output
from sysinternals_mcp.tools.autoruns import autoruns, parse_autoruns_output


@pytest.fixture(autouse=True)
def _reset() -> None:
    binary_locator.reset_cache()
    yield
    binary_locator.reset_cache()


def test_parser_loads_tsv(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "autorunsc.csv").read_text(encoding="utf-8")

    df = parse_autorunsc_output(text)

    assert not df.empty
    assert "Entry Location" in df.columns
    assert "Signer" in df.columns
    assert "Image Path" in df.columns
    assert "Launch String" in df.columns
    assert (df["Entry"] == "OneDrive").any()
    assert (df["Entry"] == "SuspiciousLauncher").any()


def test_parser_skips_banner_lines() -> None:
    text = (
        "Sysinternals Autoruns v14.10\n"
        "Copyright (C) 2002-2024 Mark Russinovich\n"
        "Time\tEntry Location\tEntry\tEnabled\n"
        "01/15/2025\tHKLM\\foo\\Run\tBar\tenabled\n"
    )
    df = parse_autorunsc_output(text)
    assert len(df) == 1
    assert df["Entry"][0] == "Bar"


def test_parser_returns_empty_for_blank() -> None:
    assert parse_autorunsc_output("").empty


def test_parser_returns_empty_when_no_header() -> None:
    assert parse_autorunsc_output("Just\nsome\nrandom text\n").empty


def test_parse_autoruns_output_tool(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "autorunsc.csv").read_text(encoding="utf-8")
    out = parse_autoruns_output(text)
    assert "**Autoruns**" in out
    assert "OneDrive" in out
    assert "SuspiciousLauncher" in out


def test_parse_autoruns_output_filter_narrows(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "autorunsc.csv").read_text(encoding="utf-8")
    out = parse_autoruns_output(text, filter="suspicious")
    assert "SuspiciousLauncher" in out
    assert "OneDrive" not in out


def test_parse_autoruns_output_filter_no_match(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "autorunsc.csv").read_text(encoding="utf-8")
    out = parse_autoruns_output(text, filter="no-such-thing-zzz")
    assert "No autorunsc entries matched filter" in out


def test_parse_autoruns_output_empty() -> None:
    out = parse_autoruns_output("")
    assert "Empty input" in out


def test_autoruns_remote_emits_lablink_first_block() -> None:
    out = autoruns(target="remote")
    assert "**Recommended dispatch:** LabLink" in out
    assert "```powershell" in out
    assert "```json" in out
    assert "autorunsc.exe" in out
    assert "-ct" in out
    assert "-a" in out
    assert "-s" in out
    assert '"parse_with": "parse_autoruns_output"' in out


def test_autoruns_remote_with_category_inserts_flag() -> None:
    out = autoruns(target="remote", category="l")
    assert "-a l" in out or " l " in out


def test_autoruns_rejects_unknown_target() -> None:
    out = autoruns(target="cluster")
    assert "Unknown target" in out
