"""Tests for coreinfo parser + MCP tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from sysinternals_mcp import binary_locator
from sysinternals_mcp.parsing.coreinfo_parser import parse_coreinfo_output
from sysinternals_mcp.tools.coreinfo import (
    coreinfo,
    parse_coreinfo_output as parse_coreinfo_tool,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    binary_locator.reset_cache()
    yield
    binary_locator.reset_cache()


def test_parser_loads_fixture(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "coreinfo.txt").read_text(encoding="utf-8")
    s = parse_coreinfo_output(text)
    assert s.header_lines  # banner + model
    assert s.features
    assert s.topology_maps
    feature_names = {f["Feature"] for f in s.features}
    assert "HTT" in feature_names
    assert "VMX" in feature_names
    # HTT supported, HYPERVISOR not supported
    htt = next(f for f in s.features if f["Feature"] == "HTT")
    assert htt["Supported"] == "yes"
    hyp = next(f for f in s.features if f["Feature"] == "HYPERVISOR")
    assert hyp["Supported"] == "no"
    # Topology maps include Socket and NUMA Node
    map_names = {m["Map"] for m in s.topology_maps}
    assert "Logical Processor to Socket Map" in map_names
    assert "Logical Processor to NUMA Node Map" in map_names


def test_parser_returns_empty_for_blank() -> None:
    s = parse_coreinfo_output("")
    assert s.header_lines == []
    assert s.features == []
    assert s.topology_maps == []


def test_parse_coreinfo_output_tool(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "coreinfo.txt").read_text(encoding="utf-8")
    out = parse_coreinfo_tool(text)
    assert "**Feature flags**" in out
    assert "**Topology maps**" in out
    assert "HTT" in out
    assert "Socket 0" in out


def test_parse_coreinfo_output_tool_empty() -> None:
    out = parse_coreinfo_tool("")
    assert "Empty input" in out


def test_coreinfo_remote_emits_lablink_first_block() -> None:
    out = coreinfo(target="remote")
    assert "**Recommended dispatch:** LabLink" in out
    assert "```powershell" in out
    assert "```json" in out
    assert "coreinfo.exe" in out
    assert '"parse_with": "parse_coreinfo_output"' in out


def test_coreinfo_rejects_unknown_target() -> None:
    out = coreinfo(target="cluster")
    assert "Unknown target" in out
