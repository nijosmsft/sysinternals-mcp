"""Tests for accesschk parser + MCP tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from sysinternals_mcp import binary_locator
from sysinternals_mcp.parsing.accesschk_parser import parse_accesschk_text
from sysinternals_mcp.tools.accesschk import accesschk, parse_accesschk_output


@pytest.fixture(autouse=True)
def _reset() -> None:
    binary_locator.reset_cache()
    yield
    binary_locator.reset_cache()


def test_parser_extracts_objects_and_principals(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "accesschk.txt").read_text(encoding="utf-8")

    df = parse_accesschk_text(text)

    assert not df.empty
    assert {"Object", "Principal", "Access", "Detail"}.issubset(df.columns)
    objs = set(df["Object"].tolist())
    assert r"C:\Windows\System32" in objs
    assert r"C:\Users\testuser\Documents" in objs

    system_rows = df[df["Principal"] == r"NT AUTHORITY\SYSTEM"]
    assert not system_rows.empty
    assert (system_rows["Access"] == "RW").all()


def test_parser_attaches_detail_to_principal(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "accesschk.txt").read_text(encoding="utf-8")
    df = parse_accesschk_text(text)

    users_row = df[
        (df["Principal"] == r"BUILTIN\Users")
        & (df["Object"] == r"C:\Windows\System32")
    ]
    assert not users_row.empty
    detail = str(users_row.iloc[0]["Detail"])
    assert "FILE_GENERIC_READ" in detail
    assert "FILE_GENERIC_EXECUTE" in detail


def test_parser_returns_empty_for_banner_only() -> None:
    text = (
        "Accesschk v6.15\n"
        "Copyright (C) 2006-2022 Mark Russinovich\n"
        "Sysinternals - www.sysinternals.com\n"
    )
    df = parse_accesschk_text(text)
    assert df.empty


def test_parse_accesschk_output_tool(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "accesschk.txt").read_text(encoding="utf-8")

    out = parse_accesschk_output(text)

    assert "**accesschk" in out
    assert "BUILTIN\\Administrators" in out


def test_accesschk_remote_emits_command() -> None:
    out = accesschk(path=r"C:\Windows", access="rw", target="remote")
    assert "```powershell" in out
    assert "accesschk.exe" in out
    assert "-w" in out
    assert "parse_accesschk_output" in out


def test_accesschk_invalid_mode_returns_error() -> None:
    out = accesschk(path=r"C:\Windows", access="bogus", target="remote")
    assert "Unknown access mode" in out


def test_accesschk_invalid_target_returns_error() -> None:
    out = accesschk(path=r"C:\Windows", target="cluster")
    assert "Unknown target" in out


def test_accesschk_empty_path_returns_error() -> None:
    out = accesschk(path="", target="local")
    assert "non-empty" in out
