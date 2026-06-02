"""Tests for psinfo parser + MCP tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from sysinternals_mcp import binary_locator
from sysinternals_mcp.parsing.psinfo_parser import parse_psinfo_output
from sysinternals_mcp.tools.psinfo import (
    parse_psinfo_output as parse_psinfo_tool,
    psinfo,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    binary_locator.reset_cache()
    yield
    binary_locator.reset_cache()


def test_parser_loads_fixture(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "psinfo.txt").read_text(encoding="utf-8")
    s = parse_psinfo_output(text)
    assert s.fields
    field_names = {f["Field"] for f in s.fields}
    assert "Uptime" in field_names
    assert "Processors" in field_names
    assert "Physical memory" in field_names
    procs = next(f for f in s.fields if f["Field"] == "Processors")
    assert procs["Value"] == "80"
    # Sections
    assert "Disk volumes" in s.sections
    assert "Hotfixes" in s.sections
    assert "Applications" in s.sections
    assert any("NTFS" in line for line in s.sections["Disk volumes"])
    assert "KB5012345" in s.sections["Hotfixes"]


def test_parser_empty() -> None:
    s = parse_psinfo_output("")
    assert s.fields == []
    assert s.sections == {}


def test_parser_skips_banner_and_systeminfo_header() -> None:
    text = (
        "PsInfo v1.79\n"
        "Copyright (C) Mark Russinovich\n"
        "Sysinternals\n"
        "System information for \\\\HOST:\n"
        "Uptime:    1 day\n"
    )
    s = parse_psinfo_output(text)
    assert len(s.fields) == 1
    assert s.fields[0]["Field"] == "Uptime"
    assert s.fields[0]["Value"] == "1 day"


def test_parse_psinfo_output_tool(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "psinfo.txt").read_text(encoding="utf-8")
    out = parse_psinfo_tool(text)
    assert "**System info**" in out
    assert "Processors" in out
    assert "Disk volumes" in out
    assert "Hotfixes" in out


def test_parse_psinfo_output_tool_empty() -> None:
    out = parse_psinfo_tool("")
    assert "Empty input" in out


def test_psinfo_remote_emits_lablink_first_block() -> None:
    out = psinfo(target="remote")
    assert "**Recommended dispatch:** LabLink" in out
    assert "```powershell" in out
    assert "```json" in out
    assert "psinfo.exe" in out
    assert "-d" in out
    assert "-s" in out
    assert "-h" in out
    assert '"parse_with": "parse_psinfo_output"' in out


def test_psinfo_remote_fast_mode_skips_extra_flags() -> None:
    out = psinfo(target="remote", full=False)
    assert "psinfo.exe" in out
    # Don't add disk/software/hotfix flags when full=False
    powershell_block = out.split("```powershell")[1].split("```")[0]
    assert " -d " not in powershell_block
    assert " -s " not in powershell_block
    assert " -h " not in powershell_block


def test_psinfo_rejects_unknown_target() -> None:
    out = psinfo(target="cluster")
    assert "Unknown target" in out
