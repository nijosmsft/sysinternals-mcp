"""Tests for sysinternals_mcp.tools.setup."""

from __future__ import annotations

from pathlib import Path

import pytest

from sysinternals_mcp import binary_locator, eula
from sysinternals_mcp.tools.setup import check_sysinternals_setup


@pytest.fixture(autouse=True)
def _reset() -> None:
    binary_locator.reset_cache()
    eula.reset_probe()
    yield
    binary_locator.reset_cache()
    eula.reset_probe()


def test_local_table_lists_every_known_binary(fake_sysinternals_dir: Path) -> None:
    eula.set_probe(lambda _: True)

    out = check_sysinternals_setup(target="local")

    for name in binary_locator.KNOWN_BINARIES:
        assert name in out
    assert "yes" in out  # EULA accepted column
    assert "ok" in out  # action when nothing to do


def test_local_table_emits_reg_add_for_unaccepted(
    fake_sysinternals_dir: Path,
) -> None:
    eula.set_probe(lambda _: False)

    out = check_sysinternals_setup(target="local")

    assert "no" in out
    assert "reg add" in out
    assert "EulaAccepted" in out


def test_remote_target_returns_powershell_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SYSINTERNALS_MCP_DIR", raising=False)

    out = check_sysinternals_setup(target="remote")

    assert "```powershell" in out
    assert "Get-ItemProperty" in out
    assert "EulaAccepted" in out
    # Remote-target output must NEVER execute the local probe.
    assert "**Sysinternals setup -- local probe**" not in out


def test_invalid_target_returns_friendly_error() -> None:
    out = check_sysinternals_setup(target="cluster")
    assert "Unknown target" in out
    assert "local" in out
    assert "remote" in out


def test_local_shows_not_found_when_binary_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Empty dir, no binaries.
    monkeypatch.setenv("SYSINTERNALS_MCP_DIR", str(tmp_path))
    monkeypatch.setattr(
        binary_locator,
        "DEFAULT_PATHS",
        (str(tmp_path / "absent"),),
    )

    # Defang shutil.which so we don't accidentally pick up a real binary
    # on the dev box's PATH.
    monkeypatch.setattr(
        binary_locator.shutil,
        "which",
        lambda _name: None,
    )
    binary_locator.reset_cache()

    out = check_sysinternals_setup(target="local")

    assert "*not found*" in out
    assert "Install Sysinternals" in out
