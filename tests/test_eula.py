"""Tests for sysinternals_mcp.eula."""

from __future__ import annotations

import pytest

from sysinternals_mcp import eula


@pytest.fixture(autouse=True)
def _reset_probe() -> None:
    eula.reset_probe()
    yield
    eula.reset_probe()


def test_tool_subkey_known_names() -> None:
    assert eula.tool_subkey("handle.exe") == "Handle"
    assert eula.tool_subkey("sigcheck.exe") == "Sigcheck"
    assert eula.tool_subkey("pslist.exe") == "PsList"
    assert eula.tool_subkey("accesschk.exe") == "AccessChk"
    assert eula.tool_subkey("procmon.exe") == "Process Monitor"
    # v0.2 additions
    assert eula.tool_subkey("tcpvcon.exe") == "TcpView"
    assert eula.tool_subkey("autorunsc.exe") == "AutoRuns"
    assert eula.tool_subkey("coreinfo.exe") == "Coreinfo"
    assert eula.tool_subkey("listdlls.exe") == "ListDLLs"
    assert eula.tool_subkey("procdump.exe") == "ProcDump"
    assert eula.tool_subkey("psinfo.exe") == "PsInfo"
    assert eula.tool_subkey("strings.exe") == "Strings"


def test_accept_command_machine_scope() -> None:
    cmd = eula.accept_command("handle.exe", scope="machine")
    assert "HKLM" in cmd
    assert "HKCU" not in cmd
    assert "Handle" in cmd


def test_is_eula_pre_accepted_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(eula.EULA_PRE_ACCEPT_ENV_VAR, raising=False)
    assert eula.is_eula_pre_accepted() is False
    for val in ("1", "true", "yes", "on", "TRUE", "Yes"):
        monkeypatch.setenv(eula.EULA_PRE_ACCEPT_ENV_VAR, val)
        assert eula.is_eula_pre_accepted() is True, val
    for val in ("0", "false", "no", "", "maybe"):
        monkeypatch.setenv(eula.EULA_PRE_ACCEPT_ENV_VAR, val)
        assert eula.is_eula_pre_accepted() is False, val


def test_tool_subkey_unknown_name_titlecases() -> None:
    assert eula.tool_subkey("psloggedon.exe") == "Psloggedon"


def test_reg_path_uses_hkcu_root() -> None:
    assert eula.reg_path("handle.exe") == r"Software\Sysinternals\Handle"


def test_accept_command_targets_hkcu() -> None:
    cmd = eula.accept_command("handle.exe")
    assert cmd.startswith("reg add ")
    assert "HKCU" in cmd
    assert "Handle" in cmd
    assert "EulaAccepted" in cmd
    assert "REG_DWORD" in cmd


def test_is_accepted_uses_injected_probe() -> None:
    seen: list[str] = []

    def fake(name: str) -> bool:
        seen.append(name)
        return name == "handle.exe"

    eula.set_probe(fake)
    assert eula.is_accepted("handle.exe") is True
    assert eula.is_accepted("sigcheck.exe") is False
    assert seen == ["handle.exe", "sigcheck.exe"]


def test_reset_probe_restores_winreg_probe() -> None:
    eula.set_probe(lambda _: True)
    assert eula.is_accepted("handle.exe") is True
    eula.reset_probe()
    # After reset, the live winreg probe runs. On a test box without
    # the Sysinternals keys this returns False; on a dev box it may
    # legitimately be True. Either way, calling it must not raise.
    result = eula.is_accepted("handle.exe")
    assert isinstance(result, bool)
