"""Tests for bootstrap + EULA-consent UX (v0.2 headline feature)."""

from __future__ import annotations

import os

import pytest

from sysinternals_mcp.binary_locator import KNOWN_BINARIES
from sysinternals_mcp.eula import EULA_PRE_ACCEPT_ENV_VAR
from sysinternals_mcp.install import (
    DEFAULT_INSTALL_DIR,
    EULA_URL,
    LIVE_BASE_URL,
    SUITE_ZIP_URL,
    SUITE_ZIP_URL_ARM64,
    WINGET_PACKAGE_ID,
    build_install_script,
    consent_required_markdown,
    probe_script,
)
from sysinternals_mcp.tools.bootstrap import bootstrap_sysinternals
from sysinternals_mcp.tools.eula_tool import accept_sysinternals_eula


@pytest.fixture(autouse=True)
def _clear_env() -> None:
    saved = os.environ.pop(EULA_PRE_ACCEPT_ENV_VAR, None)
    try:
        yield
    finally:
        if saved is not None:
            os.environ[EULA_PRE_ACCEPT_ENV_VAR] = saved


# ---------------- consent block ----------------


def test_consent_block_contains_required_anchors() -> None:
    md = consent_required_markdown()
    assert "**CONSENT REQUIRED — Sysinternals Software License Terms**" in md
    assert EULA_URL in md
    assert "Please ask the user" in md
    # Three response options
    assert "Yes" in md
    assert "No-but-install" in md
    assert "Skip-future-prompts" in md
    # Render as a 3-row table
    assert "| Option | What it does |" in md


# ---------------- install scripts ----------------


def test_zip_script_uses_arch_branch_and_suite_urls() -> None:
    script = build_install_script("zip", DEFAULT_INSTALL_DIR, accept_eula=False)
    assert script is not None
    assert "PROCESSOR_ARCHITECTURE" in script
    assert "ARM64" in script
    assert SUITE_ZIP_URL in script
    assert SUITE_ZIP_URL_ARM64 in script
    assert "Invoke-WebRequest" in script
    assert "Expand-Archive" in script
    # No EULA block when accept_eula=False
    assert "EulaAccepted" not in script


def test_zip_script_pre_accepts_when_accept_eula_true() -> None:
    script = build_install_script("zip", DEFAULT_INSTALL_DIR, accept_eula=True)
    assert script is not None
    # Pre-accepts via Start-Process -accepteula for each binary
    for binary in KNOWN_BINARIES:
        assert binary in script


def test_winget_script_uses_package_id_and_documents_server_core_caveat() -> None:
    script = build_install_script("winget", DEFAULT_INSTALL_DIR, accept_eula=True)
    assert script is not None
    assert WINGET_PACKAGE_ID in script
    assert "winget install" in script
    assert "Server Core" in script


def test_live_script_pulls_each_binary_individually() -> None:
    script = build_install_script("live", DEFAULT_INSTALL_DIR, accept_eula=False)
    assert script is not None
    assert LIVE_BASE_URL in script
    for binary in KNOWN_BINARIES:
        assert binary in script


def test_build_install_script_unknown_method_returns_none() -> None:
    assert build_install_script("nope", DEFAULT_INSTALL_DIR, False) is None


def test_probe_script_checks_well_known_binaries() -> None:
    p = probe_script(DEFAULT_INSTALL_DIR)
    assert "handle.exe" in p
    assert "procmon.exe" in p


# ---------------- bootstrap_sysinternals ----------------


def test_bootstrap_default_shows_consent_required() -> None:
    out = bootstrap_sysinternals(target="local")
    assert "CONSENT REQUIRED" in out
    # No install script when consent is missing
    assert "Invoke-WebRequest" not in out


def test_bootstrap_accept_eula_renders_local_install_block() -> None:
    out = bootstrap_sysinternals(target="local", accept_eula=True)
    assert "CONSENT REQUIRED" not in out
    assert "Install step" in out
    assert "```powershell" in out
    assert "Invoke-WebRequest" in out
    assert "Skip-if-already-installed probe" in out
    # Defaults applied
    assert DEFAULT_INSTALL_DIR in out


def test_bootstrap_force_skips_probe_block() -> None:
    out = bootstrap_sysinternals(target="local", accept_eula=True, force=True)
    assert "Install step" in out
    assert "Skip-if-already-installed probe" not in out


def test_bootstrap_env_var_pre_accept_path() -> None:
    os.environ[EULA_PRE_ACCEPT_ENV_VAR] = "1"
    out = bootstrap_sysinternals(target="local")
    assert "CONSENT REQUIRED" not in out
    assert "treating `accept_eula` as True" in out
    assert "Invoke-WebRequest" in out


def test_bootstrap_remote_emits_lablink_first_block() -> None:
    out = bootstrap_sysinternals(target="remote", accept_eula=True)
    assert "**Recommended dispatch:** LabLink" in out
    assert "```powershell" in out
    assert "```json" in out


def test_bootstrap_winget_method_notes_server_core_caveat() -> None:
    out = bootstrap_sysinternals(
        target="local", install_method="winget", accept_eula=True
    )
    assert "winget" in out
    assert "Server Core" in out


def test_bootstrap_live_method_pulls_each_binary() -> None:
    out = bootstrap_sysinternals(
        target="local", install_method="live", accept_eula=True
    )
    assert LIVE_BASE_URL in out
    for binary in ("handle.exe", "procmon.exe"):
        assert binary in out


def test_bootstrap_rejects_unknown_install_method() -> None:
    out = bootstrap_sysinternals(
        target="local", install_method="garbage", accept_eula=True
    )
    assert "Unknown install_method" in out


def test_bootstrap_rejects_unknown_target() -> None:
    out = bootstrap_sysinternals(target="cluster", accept_eula=True)
    assert "Unknown target" in out


# ---------------- accept_sysinternals_eula ----------------


def test_accept_eula_user_scope_emits_hkcu_for_each_binary() -> None:
    from sysinternals_mcp.eula import tool_subkey

    out = accept_sysinternals_eula(target="local", scope="user")
    assert "HKCU\\Software\\Sysinternals" in out
    assert "reg add" in out
    # Once per known binary — assert subkey (display name) appears
    for binary in KNOWN_BINARIES:
        assert tool_subkey(binary) in out


def test_accept_eula_machine_scope_emits_hklm_and_elevation_note() -> None:
    out = accept_sysinternals_eula(target="local", scope="machine")
    assert "HKLM" in out
    assert "elevated" in out.lower()


def test_accept_eula_remote_emits_lablink_first_block() -> None:
    out = accept_sysinternals_eula(target="remote", scope="user")
    assert "**Recommended dispatch:** LabLink" in out
    assert "```powershell" in out
    assert "```json" in out


def test_accept_eula_rejects_unknown_scope() -> None:
    out = accept_sysinternals_eula(target="local", scope="bogus")
    assert "Unknown scope" in out


def test_accept_eula_rejects_unknown_target() -> None:
    out = accept_sysinternals_eula(target="cluster", scope="user")
    assert "Unknown target" in out
