"""Shared pytest fixtures for the sysinternals-mcp test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Path to the bundled fixture directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_sysinternals_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway directory pretending to hold the Sysinternals install.

    Creates empty stub files for every binary the server knows about and
    points ``SYSINTERNALS_MCP_DIR`` at the directory. Used by tests that
    exercise binary discovery without invoking a real subprocess.
    """
    binaries = (
        "handle.exe",
        "sigcheck.exe",
        "pslist.exe",
        "accesschk.exe",
        "procmon.exe",
    )
    for name in binaries:
        (tmp_path / name).write_bytes(b"")
    monkeypatch.setenv("SYSINTERNALS_MCP_DIR", str(tmp_path))
    # Reset the locator cache so the env var takes effect.
    from sysinternals_mcp import binary_locator

    binary_locator.reset_cache()
    return tmp_path
