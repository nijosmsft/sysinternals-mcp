"""Tests for ProcMon recipe metadata + procmon MCP tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from sysinternals_mcp import binary_locator
from sysinternals_mcp.parsing.pml_parser import _classify_op, summarize_csv
from sysinternals_mcp.profiles import metadata
from sysinternals_mcp.tools.procmon import (
    analyze_pml,
    get_capture_instructions,
    get_procmon_capture_commands,
    get_procmon_recipe,
    list_procmon_recipes,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    binary_locator.reset_cache()
    yield
    binary_locator.reset_cache()


def test_three_recipes_ship() -> None:
    recipes = metadata.list_recipes()
    names = {r.recipe for r in recipes}
    assert names == {"file_io_only", "network_only", "process_lifecycle"}


def test_each_recipe_has_a_loadable_descriptor() -> None:
    for r in metadata.list_recipes():
        text = metadata.load_descriptor_text(r)
        assert text.strip()
        # Sanity check: descriptors document include/exclude sections.
        assert "Includes" in text
        assert "Excludes" in text


def test_list_procmon_recipes_returns_markdown() -> None:
    out = list_procmon_recipes()
    assert "**ProcMon recipes**" in out
    for name in ("file_io_only", "network_only", "process_lifecycle"):
        assert name in out


def test_get_procmon_recipe_renders_descriptor() -> None:
    out = get_procmon_recipe("file_io_only")
    assert "file_io_only" in out
    assert "When to use" in out
    assert "Filter" in out
    assert "Includes" in out  # from the descriptor body


def test_get_procmon_recipe_unknown() -> None:
    out = get_procmon_recipe("nonsense")
    assert "Unknown recipe" in out


def test_capture_commands_remote_emits_block() -> None:
    out = get_procmon_capture_commands(
        recipe="network_only",
        output_path=r"C:\tmp\net.pml",
        duration_s=30,
        target="remote",
    )

    assert "```powershell" in out
    assert "procmon.exe" in out
    assert "/BackingFile" in out
    assert r"C:\tmp\net.pml" in out
    assert "/Runtime" in out
    assert "30" in out


def test_capture_commands_unknown_recipe() -> None:
    out = get_procmon_capture_commands(recipe="nope", target="remote")
    assert "Unknown recipe" in out


def test_capture_instructions_local_runbook() -> None:
    out = get_capture_instructions(
        recipe="file_io_only", target="local", output_path=r"C:\tmp\fio.pml"
    )

    assert "# Local ProcMon capture runbook" in out
    assert "check_sysinternals_setup" in out
    assert "analyze_pml" in out
    assert r"C:\tmp\fio.pml" in out


def test_capture_instructions_remote_names_three_transports() -> None:
    """The runbook must name PSRemoting, LabLink (as one example), and manual."""
    out = get_capture_instructions(
        recipe="process_lifecycle",
        target="remote",
        output_path=r"C:\tmp\proc.pml",
    )

    assert "# Remote ProcMon capture runbook" in out
    assert "PSRemoting" in out
    # Naming LabLink in docs is OK; coupling in source is not.
    assert "LabLink" in out
    # Make sure we describe it as "one example", not the default.
    assert "any other agent" in out or "no dependency" in out
    assert "Manual" in out or "SMB" in out


def test_classify_op_buckets() -> None:
    assert _classify_op("TCP Connect") == "Network"
    assert _classify_op("UDP Send") == "Network"
    assert _classify_op("CreateFile") == "File"
    assert _classify_op("QueryDirectory") == "File"
    assert _classify_op("RegQueryValue") == "Registry"
    assert _classify_op("Process Create") == "Process"
    assert _classify_op("Load Image") == "Image Load"
    assert _classify_op("Unknown") == "Other"


def test_summarize_csv_against_fixture(fixtures_dir: Path) -> None:
    summary = summarize_csv(fixtures_dir / "procmon.csv", top_n=5)

    assert summary.total_rows == 10
    assert not summary.top_processes.empty
    top_proc_names = summary.top_processes["Process Name"].tolist()
    assert "chrome.exe" in top_proc_names
    classes = summary.op_class_counts["Class"].tolist()
    assert "File" in classes
    assert "Network" in classes
    assert "Process" in classes
    # Two non-success results: NAME NOT FOUND, ACCESS DENIED.
    assert summary.error_count == 2


def test_analyze_pml_missing_file_returns_error() -> None:
    out = analyze_pml(path=r"C:\does\not\exist.pml")
    assert "does not exist" in out


def test_analyze_pml_wrong_extension_returns_error(tmp_path: Path) -> None:
    f = tmp_path / "notpml.csv"
    f.write_text("x", encoding="utf-8")

    out = analyze_pml(path=str(f))

    assert "does not look like" in out


def test_analyze_pml_empty_path() -> None:
    out = analyze_pml(path="")
    assert "non-empty" in out


def test_analyze_pml_uses_procmon(
    fake_sysinternals_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    fixtures_dir: Path,
    tmp_path: Path,
) -> None:
    """Stub procmon's CSV conversion and verify analyze_pml stitches it together."""
    pml = tmp_path / "fake.pml"
    pml.write_bytes(b"")  # existence is all that matters; converter is stubbed.

    def fake_convert(_procmon: Path, _pml: Path, csv: Path, timeout: int = 600) -> None:
        csv.write_text(
            (fixtures_dir / "procmon.csv").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    from sysinternals_mcp.parsing import pml_parser

    monkeypatch.setattr(pml_parser, "convert_pml_to_csv", fake_convert)

    out = analyze_pml(path=str(pml), top_n=5)

    assert "ProcMon summary" in out
    assert "chrome.exe" in out
    assert "Event class histogram" in out
