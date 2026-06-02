"""Tests for handle parser + handle MCP tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from sysinternals_mcp import binary_locator, eula
from sysinternals_mcp.parsing.handle_parser import (
    parse_handle_text,
    summarize_handles,
)
from sysinternals_mcp.tools.handle import handle_list, parse_handle_output


@pytest.fixture(autouse=True)
def _reset() -> None:
    binary_locator.reset_cache()
    eula.reset_probe()
    yield
    binary_locator.reset_cache()
    eula.reset_probe()


def test_parser_extracts_handles(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "handle.txt").read_text(encoding="utf-8")

    df = parse_handle_text(text)

    assert not df.empty
    assert {"Process", "PID", "Handle", "Type", "Access", "Name"}.issubset(df.columns)
    assert "explorer.exe" in df["Process"].tolist()
    assert "chrome.exe" in df["Process"].tolist()
    assert 4520 in df["PID"].tolist()
    assert 7892 in df["PID"].tolist()
    # File rows have Access; Key rows have empty Access.
    file_rows = df[df["Type"] == "File"]
    assert not file_rows.empty
    assert (file_rows["Access"] != "").any()


def test_parser_returns_empty_frame_for_banner_only() -> None:
    text = (
        "Nthandle v5.0 - Handle viewer\n"
        "Copyright (C) ...\n"
        "Sysinternals - www.sysinternals.com\n"
    )
    df = parse_handle_text(text)
    assert df.empty
    assert list(df.columns) == [
        "Process",
        "PID",
        "User",
        "Handle",
        "Type",
        "Access",
        "Name",
    ]


def test_summarize_handles_groups_correctly(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "handle.txt").read_text(encoding="utf-8")
    df = parse_handle_text(text)

    summary = summarize_handles(df)

    assert {"Process", "PID", "Type", "Count"}.issubset(summary.columns)
    chrome_files = summary[
        (summary["Process"] == "chrome.exe") & (summary["Type"] == "File")
    ]
    assert not chrome_files.empty


def test_parse_handle_output_tool_returns_markdown(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "handle.txt").read_text(encoding="utf-8")

    out = parse_handle_output(text)

    assert "**Handles for" in out
    assert "| Process |" in out
    assert "chrome.exe" in out
    assert "explorer.exe" in out


def test_parse_handle_output_handles_empty_input() -> None:
    out = parse_handle_output("")
    assert "Empty input" in out


def test_handle_list_remote_emits_powershell_block() -> None:
    out = handle_list(process="chrome", target="remote")
    assert "```powershell" in out
    assert "handle.exe" in out
    assert "-p chrome" in out
    assert "parse_handle_output" in out


def test_handle_list_invalid_target_returns_error() -> None:
    out = handle_list(process="*", target="bogus")
    assert "Unknown target" in out


def test_handle_list_missing_binary_returns_friendly_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SYSINTERNALS_MCP_DIR", str(tmp_path))
    monkeypatch.setattr(binary_locator.shutil, "which", lambda _n: None)
    monkeypatch.setattr(binary_locator, "DEFAULT_PATHS", (str(tmp_path / "x"),))
    binary_locator.reset_cache()

    out = handle_list(process="chrome", target="local")

    assert "handle.exe" in out
    assert "not found" in out
    assert "SYSINTERNALS_MCP_DIR" in out
