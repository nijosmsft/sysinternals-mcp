"""Tests for accesschk reg + svc presets added in v0.2."""

from __future__ import annotations

from pathlib import Path

import pytest

from sysinternals_mcp import binary_locator
from sysinternals_mcp.tools.accesschk import (
    _ACCESS_MODES,
    _build_cmdline,
    accesschk,
    parse_accesschk_output,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    binary_locator.reset_cache()
    yield
    binary_locator.reset_cache()


def test_reg_preset_uses_dash_k_flag() -> None:
    flags = _ACCESS_MODES["reg"]
    assert "-k" in flags
    assert "-w" in flags  # carry write triage default
    assert "-q" in flags


def test_svc_preset_uses_dash_c_flag() -> None:
    flags = _ACCESS_MODES["svc"]
    assert "-c" in flags
    assert "-q" in flags


def test_build_cmdline_reg_emits_dash_k() -> None:
    cmd = _build_cmdline("accesschk.exe", "HKLM\\SYSTEM\\CurrentControlSet", "reg")
    assert isinstance(cmd, list)
    assert "-k" in cmd
    assert "HKLM\\SYSTEM\\CurrentControlSet" in cmd


def test_build_cmdline_svc_emits_dash_c() -> None:
    cmd = _build_cmdline("accesschk.exe", "Spooler", "svc")
    assert isinstance(cmd, list)
    assert "-c" in cmd
    assert "Spooler" in cmd


def test_accesschk_remote_reg_includes_dash_k() -> None:
    out = accesschk(
        path="HKLM\\SYSTEM\\CurrentControlSet\\Services",
        access="reg",
        target="remote",
    )
    assert "accesschk" in out
    assert "-k" in out
    assert "HKLM" in out
    assert "access=`reg`" in out


def test_accesschk_remote_svc_includes_dash_c() -> None:
    out = accesschk(path="Spooler", access="svc", target="remote")
    assert "accesschk" in out
    assert "-c" in out
    assert "Spooler" in out
    assert "access=`svc`" in out


def test_parse_accesschk_output_reg_fixture(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "accesschk_reg.txt").read_text(encoding="utf-8")
    out = parse_accesschk_output(
        text, path="HKLM\\SYSTEM\\CurrentControlSet", access="reg"
    )
    assert "accesschk" in out
    assert "HKLM" in out
    assert "mode=`reg`" in out


def test_parse_accesschk_output_svc_fixture(fixtures_dir: Path) -> None:
    text = (fixtures_dir / "accesschk_svc.txt").read_text(encoding="utf-8")
    out = parse_accesschk_output(text, path="Spooler", access="svc")
    assert "accesschk" in out
    assert "Spooler" in out
    assert "mode=`svc`" in out


def test_help_text_lists_reg_and_svc_modes() -> None:
    # Unknown mode error message should now list reg/svc as valid.
    out = accesschk(path="x", access="bogus", target="local")
    assert "reg" in out
    assert "svc" in out
