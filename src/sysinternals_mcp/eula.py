"""EULA probe and accept-command helpers.

Sysinternals binaries write
``HKCU\\Software\\Sysinternals\\<Tool>\\EulaAccepted=1`` after the first
run with ``-accepteula``. This module:

- Reads the HKCU value for a given tool (returns ``False`` when the key
  is absent or on non-Windows hosts).
- Emits the exact ``reg add`` command an operator can paste to
  pre-accept the EULA under the running account, useful when the MCP
  server runs under a service account different from the interactive
  user.

The probe is HKCU-scoped because that is where Sysinternals writes the
flag — there is no machine-wide equivalent.
"""

from __future__ import annotations

import sys
from typing import Callable

# winreg is Windows-only. Tests on non-Windows hosts get a stub that
# always reports ``not accepted`` so the rest of the module still loads.
if sys.platform == "win32":
    import winreg  # type: ignore[import-not-found]
else:  # pragma: no cover — exercised in CI when the matrix grows
    winreg = None  # type: ignore[assignment]


SYSINTERNALS_REG_ROOT = r"Software\Sysinternals"


def tool_subkey(tool_name: str) -> str:
    """Return the canonical Sysinternals subkey for a tool name.

    Sysinternals writes the per-tool subkey using the tool's display
    name (no ``.exe``), with the first letter title-cased. The map is
    a 1:1 lookup for the binaries we know about.
    """
    stem = tool_name.lower()
    if stem.endswith(".exe"):
        stem = stem[:-4]
    return {
        "handle": "Handle",
        "sigcheck": "Sigcheck",
        "pslist": "PsList",
        "accesschk": "AccessChk",
        "procmon": "Process Monitor",
    }.get(stem, stem.capitalize())


def reg_path(tool_name: str) -> str:
    """Return the full HKCU subkey path for the tool's EULA flag."""
    return f"{SYSINTERNALS_REG_ROOT}\\{tool_subkey(tool_name)}"


# Type alias for tests that inject a fake probe.
ProbeFn = Callable[[str], bool]


def _winreg_probe(tool_name: str) -> bool:
    """Read the live HKCU value. Returns False on any error / missing key."""
    if winreg is None:  # non-Windows guard
        return False
    try:
        with winreg.OpenKey(  # type: ignore[union-attr]
            winreg.HKEY_CURRENT_USER,  # type: ignore[union-attr]
            reg_path(tool_name),
        ) as key:
            value, _ = winreg.QueryValueEx(key, "EulaAccepted")  # type: ignore[union-attr]
            return int(value) == 1
    except OSError:
        return False


_probe: ProbeFn = _winreg_probe


def set_probe(fn: ProbeFn) -> None:
    """Inject a probe function. Tests use this to stub the registry."""
    global _probe
    _probe = fn


def reset_probe() -> None:
    """Restore the live winreg-backed probe."""
    global _probe
    _probe = _winreg_probe


def is_accepted(tool_name: str) -> bool:
    """Return True when ``HKCU\\Software\\Sysinternals\\<Tool>\\EulaAccepted == 1``."""
    return _probe(tool_name)


def accept_command(tool_name: str) -> str:
    """Return a paste-ready ``reg add`` command that pre-accepts the EULA.

    The emitted command targets HKCU so it accepts the EULA under the
    running account — exactly what the MCP server needs when it runs
    as a service under a non-interactive identity.
    """
    return (
        f'reg add "HKCU\\{reg_path(tool_name)}" '
        f'/v EulaAccepted /t REG_DWORD /d 1 /f'
    )


__all__ = [
    "SYSINTERNALS_REG_ROOT",
    "accept_command",
    "is_accepted",
    "reg_path",
    "reset_probe",
    "set_probe",
    "tool_subkey",
]
