"""Tests for listdlls + procdump + strings."""

from __future__ import annotations

from pathlib import Path

import pytest

from sysinternals_mcp import binary_locator
from sysinternals_mcp.parsing.listdlls_parser import (
    parse_listdlls_text,
    summarize_listdlls,
)
from sysinternals_mcp.parsing.procdump_parser import parse_procdump_output
from sysinternals_mcp.parsing.strings_parser import parse_strings_output
from sysinternals_mcp.tools.listdlls import (
    listdlls,
    parse_listdlls_output as parse_listdlls_tool,
)
from sysinternals_mcp.tools.procdump import (
    parse_procdump_output as parse_procdump_tool,
    procdump,
)
from sysinternals_mcp.tools.strings import (
    parse_strings_output as parse_strings_tool,
    strings as strings_tool,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    binary_locator.reset_cache()
    yield
    binary_locator.reset_cache()


# ---------------- listdlls ----------------


def test_listdlls_parser(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "listdlls.txt").read_text(encoding="utf-8")
    df = parse_listdlls_text(text)
    assert len(df) == 7
    assert set(df["Process"]) == {"explorer.exe", "notepad.exe"}
    assert set(df["PID"]) == {"3204", "5120"}
    assert df["Path"].iloc[0].endswith("explorer.exe")


def test_listdlls_parser_empty() -> None:
    df = parse_listdlls_text("")
    assert df.empty
    assert list(df.columns) == ["Process", "PID", "Base", "Size", "Path"]


def test_listdlls_summary(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "listdlls.txt").read_text(encoding="utf-8")
    df = parse_listdlls_text(text)
    s = summarize_listdlls(df)
    assert len(s) == 2
    explorer_row = s[s["Process"] == "explorer.exe"].iloc[0]
    assert explorer_row["DLLs"] == 4


def test_parse_listdlls_output_tool(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "listdlls.txt").read_text(encoding="utf-8")
    out = parse_listdlls_tool(text, process="*")
    assert "Per-process DLL counts" in out
    assert "First 50 DLL rows" in out
    assert "explorer.exe" in out


def test_listdlls_remote_emits_lablink_first_block() -> None:
    out = listdlls(target="remote", process="notepad.exe")
    assert "**Recommended dispatch:** LabLink" in out
    assert "```powershell" in out
    assert "```json" in out
    assert "listdlls.exe" in out
    assert "notepad.exe" in out
    assert '"parse_with": "parse_listdlls_output"' in out


def test_listdlls_rejects_unknown_target() -> None:
    out = listdlls(target="cluster")
    assert "Unknown target" in out


# ---------------- procdump ----------------


def test_procdump_parser_success(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "procdump.txt").read_text(encoding="utf-8")
    r = parse_procdump_output(text)
    assert r.success is True
    field_names = {f["Field"] for f in r.fields}
    assert "Dump path" in field_names
    assert "Dump size" in field_names
    assert "Elapsed" in field_names


def test_procdump_parser_failure_detects_error() -> None:
    text = "ProcDump v11.0\nError: Access denied\n"
    r = parse_procdump_output(text)
    assert r.success is False


def test_procdump_parser_empty() -> None:
    r = parse_procdump_output("")
    assert r.success is False
    assert r.fields == []


def test_parse_procdump_output_tool(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "procdump.txt").read_text(encoding="utf-8")
    out = parse_procdump_tool(text, process="notepad.exe", dump_path="C:\\dumps")
    assert "Status: SUCCESS" in out
    assert "Dump path" in out


def test_procdump_requires_process() -> None:
    out = procdump(target="remote", dump_path="C:\\dumps")
    assert "requires `process=`" in out


def test_procdump_requires_dump_path() -> None:
    out = procdump(target="remote", process="notepad.exe")
    assert "requires `dump_path=`" in out


def test_procdump_remote_emits_lablink_first_block() -> None:
    out = procdump(
        target="remote", process="notepad.exe", dump_path="C:\\dumps"
    )
    assert "**Recommended dispatch:** LabLink" in out
    assert "```powershell" in out
    assert "```json" in out
    assert "procdump.exe" in out
    assert "-ma" in out
    assert "notepad.exe" in out
    assert '"parse_with": "parse_procdump_output"' in out


def test_procdump_rejects_unknown_target() -> None:
    out = procdump(target="cluster", process="notepad.exe", dump_path="C:\\d")
    assert "Unknown target" in out


# ---------------- strings ----------------


def test_strings_parser(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "strings.txt").read_text(encoding="utf-8")
    df = parse_strings_output(text)
    assert len(df) >= 5
    assert all(col in df.columns for col in ("Offset", "String"))
    assert any("HelloWorld" in s for s in df["String"])


def test_strings_parser_with_offset() -> None:
    text = "Strings v2.54\n00001000: Hello\n00002000: World\n"
    df = parse_strings_output(text)
    assert len(df) == 2
    assert df["Offset"].iloc[0] == "00001000"
    assert df["String"].iloc[0] == "Hello"


def test_strings_parser_empty() -> None:
    df = parse_strings_output("")
    assert df.empty


def test_parse_strings_output_tool(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "strings.txt").read_text(encoding="utf-8")
    out = parse_strings_tool(text, path="C:\\bin\\test.exe")
    assert "Strings in" in out
    assert "HelloWorld" in out


def test_parse_strings_output_tool_with_filter(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "strings.txt").read_text(encoding="utf-8")
    out = parse_strings_tool(
        text, path="C:\\bin\\test.exe", filter="microsoft"
    )
    assert "Microsoft Corporation" in out


def test_strings_requires_path() -> None:
    out = strings_tool(target="remote")
    assert "requires `path=`" in out


def test_strings_remote_emits_lablink_first_block() -> None:
    out = strings_tool(target="remote", path="C:\\Windows\\notepad.exe")
    assert "**Recommended dispatch:** LabLink" in out
    assert "```powershell" in out
    assert "```json" in out
    assert "strings.exe" in out
    assert '"parse_with": "parse_strings_output"' in out


def test_strings_rejects_unknown_target() -> None:
    out = strings_tool(target="cluster", path="x.exe")
    assert "Unknown target" in out
