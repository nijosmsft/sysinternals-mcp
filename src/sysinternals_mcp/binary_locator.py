"""Sysinternals binary discovery.

Resolves a binary path in priority order:

1. ``SYSINTERNALS_MCP_DIR`` env var, joined with the requested name.
2. ``where.exe <name>`` (PATH lookup).
3. Default install paths: ``C:\\Sysinternals\\``,
   ``C:\\Tools\\Sysinternals\\``, ``%ProgramFiles%\\Sysinternals\\``.

Results are cached for the process lifetime. Call :func:`reset_cache`
after changing the env var (the tests do this).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

ENV_VAR = "SYSINTERNALS_MCP_DIR"

DEFAULT_PATHS: tuple[str, ...] = (
    r"C:\Sysinternals",
    r"C:\Tools\Sysinternals",
    r"%ProgramFiles%\Sysinternals",
)

# Every Sysinternals binary the server knows about. The setup tool
# walks this list; individual tool modules reference the names
# directly. Keep alphabetical.
KNOWN_BINARIES: tuple[str, ...] = (
    "accesschk.exe",
    "handle.exe",
    "pslist.exe",
    "procmon.exe",
    "sigcheck.exe",
)


_cache: dict[str, Path | None] = {}


def reset_cache() -> None:
    """Clear the in-process resolution cache. Mostly for tests."""
    _cache.clear()


def _expand(path: str) -> Path:
    return Path(os.path.expandvars(path))


def _candidates(name: str) -> list[Path]:
    """Yield candidate paths in priority order."""
    out: list[Path] = []

    env_dir = os.environ.get(ENV_VAR)
    if env_dir:
        out.append(_expand(env_dir) / name)

    which = shutil.which(name)
    if which:
        out.append(Path(which))

    for default in DEFAULT_PATHS:
        out.append(_expand(default) / name)

    return out


def find_binary(name: str) -> Path | None:
    """Return the resolved path to a Sysinternals binary, or ``None``.

    Args:
        name: Binary file name with extension, e.g. ``"handle.exe"``.

    Returns:
        A ``Path`` pointing at an existing file, or ``None`` if no
        candidate exists.
    """
    if name in _cache:
        return _cache[name]
    for candidate in _candidates(name):
        try:
            if candidate.is_file():
                _cache[name] = candidate
                return candidate
        except OSError:
            continue
    _cache[name] = None
    return None


def search_paths() -> list[str]:
    """Return the human-readable list of paths probed for a binary.

    Used by ``check_sysinternals_setup`` to surface the search order
    when nothing was found.
    """
    paths: list[str] = []
    env_dir = os.environ.get(ENV_VAR)
    if env_dir:
        paths.append(f"{ENV_VAR}={env_dir}")
    paths.append("PATH (where.exe)")
    for default in DEFAULT_PATHS:
        paths.append(default)
    return paths


__all__ = [
    "DEFAULT_PATHS",
    "ENV_VAR",
    "KNOWN_BINARIES",
    "find_binary",
    "reset_cache",
    "search_paths",
]
