"""Tests for sysinternals_mcp.binary_locator."""

from __future__ import annotations

from pathlib import Path

import pytest

from sysinternals_mcp import binary_locator


@pytest.fixture(autouse=True)
def _reset_cache_each_test() -> None:
    binary_locator.reset_cache()
    yield
    binary_locator.reset_cache()


def test_env_var_takes_priority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binary = tmp_path / "handle.exe"
    binary.write_bytes(b"")
    monkeypatch.setenv("SYSINTERNALS_MCP_DIR", str(tmp_path))

    result = binary_locator.find_binary("handle.exe")

    assert result == binary


def test_returns_none_when_nothing_resolves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No env var, no PATH hit, no default paths.
    monkeypatch.delenv("SYSINTERNALS_MCP_DIR", raising=False)
    monkeypatch.setattr(binary_locator, "shutil", _NoShutil(), raising=False)
    monkeypatch.setattr(
        binary_locator,
        "DEFAULT_PATHS",
        (str(tmp_path / "missing-dir-a"), str(tmp_path / "missing-dir-b")),
    )

    assert binary_locator.find_binary("does-not-exist.exe") is None


def test_result_is_cached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    binary = tmp_path / "pslist.exe"
    binary.write_bytes(b"")
    monkeypatch.setenv("SYSINTERNALS_MCP_DIR", str(tmp_path))

    first = binary_locator.find_binary("pslist.exe")
    # Remove the file; cached lookup should still return the old path.
    binary.unlink()
    second = binary_locator.find_binary("pslist.exe")

    assert first == second
    assert first is not None


def test_reset_cache_forces_relookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = tmp_path / "sigcheck.exe"
    binary.write_bytes(b"")
    monkeypatch.setenv("SYSINTERNALS_MCP_DIR", str(tmp_path))

    first = binary_locator.find_binary("sigcheck.exe")
    binary.unlink()
    binary_locator.reset_cache()
    second = binary_locator.find_binary("sigcheck.exe")

    assert first is not None
    assert second is None


def test_search_paths_lists_env_var_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSINTERNALS_MCP_DIR", r"C:\sysint-test")

    paths = binary_locator.search_paths()

    assert paths[0] == r"SYSINTERNALS_MCP_DIR=C:\sysint-test"
    assert "PATH (where.exe)" in paths


def test_known_binaries_includes_each_tool() -> None:
    assert "handle.exe" in binary_locator.KNOWN_BINARIES
    assert "sigcheck.exe" in binary_locator.KNOWN_BINARIES
    assert "pslist.exe" in binary_locator.KNOWN_BINARIES
    assert "accesschk.exe" in binary_locator.KNOWN_BINARIES
    assert "procmon.exe" in binary_locator.KNOWN_BINARIES


class _NoShutil:
    """Stub shutil module that always reports nothing on PATH."""

    @staticmethod
    def which(_name: str) -> str | None:
        return None
