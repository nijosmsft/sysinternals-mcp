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

import os
import sys
from typing import Callable

# Env var that lets an operator suppress the bootstrap consent prompt
# globally for an MCP server install. See
# ``bootstrap_sysinternals`` / ``accept_sysinternals_eula`` for the
# three flip paths (arg / env var / standalone tool).
EULA_PRE_ACCEPT_ENV_VAR = "SYSINTERNALS_MCP_ACCEPT_EULA"

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
        "autorunsc": "AutoRuns",
        "coreinfo": "Coreinfo",
        "listdlls": "ListDLLs",
        "procdump": "ProcDump",
        "psinfo": "PsInfo",
        "strings": "Strings",
        "tcpvcon": "TcpView",
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


def accept_command(tool_name: str, scope: str = "user") -> str:
    """Return a paste-ready ``reg add`` command that pre-accepts the EULA.

    Args:
        tool_name: Sysinternals binary name (with or without ``.exe``).
        scope: ``"user"`` (default) writes HKCU under the running
            account. ``"machine"`` writes HKLM (requires admin); useful
            when the MCP server runs as SYSTEM and a human operator
            also runs the tools interactively.
    """
    if scope == "machine":
        root = "HKLM"
    else:
        root = "HKCU"
    return (
        f'reg add "{root}\\{reg_path(tool_name)}" '
        f'/v EulaAccepted /t REG_DWORD /d 1 /f'
    )


def is_eula_pre_accepted() -> bool:
    """Return True when the operator has set the global pre-accept env var.

    When this returns True, ``bootstrap_sysinternals`` and
    ``accept_sysinternals_eula`` skip their CONSENT REQUIRED prompts
    and proceed directly to emit install / reg-add commands. This is
    the "skip this prompt for all future installs in this MCP server"
    flip path documented in the bootstrap UX.
    """
    val = os.environ.get(EULA_PRE_ACCEPT_ENV_VAR, "").strip().lower()
    return val in {"1", "true", "yes", "on"}


__all__ = [
    "EULA_PRE_ACCEPT_ENV_VAR",
    "SYSINTERNALS_REG_ROOT",
    "accept_command",
    "is_accepted",
    "is_eula_pre_accepted",
    "reg_path",
    "reset_probe",
    "set_probe",
    "tool_subkey",
]
