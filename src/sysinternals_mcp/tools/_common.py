"""Shared infrastructure for live-execute Sysinternals tool wrappers.

Every live tool (``handle_list``, ``sigcheck``, ``pslist``,
``accesschk``) follows the same pattern:

1. Validate ``target`` (``"local"`` or ``"remote"``).
2. Build the command line (binary path + ``-accepteula`` + per-tool
   args).
3. For ``"local"``: run the subprocess, capture stdout, parse, return
   markdown. For ``"remote"``: return the command as a fenced
   ```powershell``` block.
4. On any failure (binary missing, subprocess error, parse error)
   return a friendly markdown error -- never raise.

This module centralizes the boilerplate so the per-tool modules stay
short and focused on parsing.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from sysinternals_mcp.binary_locator import ENV_VAR, find_binary

VALID_TARGETS = ("local", "remote")
_DOWNLOAD_URL = "https://learn.microsoft.com/en-us/sysinternals/"


@dataclass
class CommandResult:
    """Outcome of running a Sysinternals subprocess."""

    returncode: int
    stdout: str
    stderr: str
    cmdline: list[str]


class ToolError(Exception):
    """Raised internally; helpers catch and convert to markdown."""


def validate_target(target: str) -> str | None:
    """Return a friendly error string, or ``None`` if ``target`` is valid."""
    if target not in VALID_TARGETS:
        return (
            f"Unknown target `{target}`. Valid: "
            f"{', '.join(VALID_TARGETS)}. Use `local` to run the binary "
            "on this machine, or `remote` to get a paste-ready command "
            "for another host."
        )
    return None


def require_binary(name: str) -> Path | str:
    """Locate a binary or return a friendly markdown error string."""
    path = find_binary(name)
    if path is None:
        return (
            f"`{name}` not found. Install the Sysinternals Suite from "
            f"{_DOWNLOAD_URL} and set `{ENV_VAR}` to its directory "
            "(or put the binaries on PATH). Run "
            "`check_sysinternals_setup` to confirm."
        )
    return path


def run_subprocess(cmdline: list[str], timeout: int = 60) -> CommandResult:
    """Run a command with stdout/stderr captured. Returns a CommandResult.

    Raises :class:`ToolError` on timeout or unexpected OS errors -- the
    caller is responsible for converting that to a markdown error.
    """
    try:
        completed = subprocess.run(  # noqa: S603 — we control the binary path
            cmdline,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolError(f"`{cmdline[0]}` timed out after {timeout}s") from exc
    except FileNotFoundError as exc:
        raise ToolError(f"`{cmdline[0]}` not found: {exc}") from exc
    except OSError as exc:
        raise ToolError(f"`{cmdline[0]}` failed to launch: {exc}") from exc

    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        cmdline=cmdline,
    )


def remote_command_block(cmdline: list[str], note: str = "") -> str:
    """Render a paste-ready PowerShell block for a remote target.

    The command line is quoted so spaces in paths survive a paste into a
    PowerShell prompt.
    """
    parts = [_quote(p) for p in cmdline]
    body = " ".join(parts)
    out = ["```powershell", body, "```"]
    if note:
        out.append("")
        out.append(note)
    return "\n".join(out)


def _quote(arg: str) -> str:
    """Single-quote an argument for PowerShell if it contains whitespace."""
    if not arg:
        return "''"
    if any(ch in arg for ch in (" ", "\t", '"', "'", "&", "|", "<", ">")):
        # PowerShell single-quote rules: double up embedded single quotes.
        escaped = arg.replace("'", "''")
        return f"'{escaped}'"
    return arg


def format_subprocess_error(result: CommandResult, tool: str) -> str:
    """Return a markdown error block summarizing a failed subprocess run."""
    cmdline_str = " ".join(_quote(p) for p in result.cmdline)
    stderr = result.stderr.strip()
    body = (
        f"**`{tool}` failed (exit {result.returncode})**\n"
        "\n"
        f"```text\n{cmdline_str}\n```\n"
    )
    if stderr:
        body += f"\nstderr:\n\n```text\n{stderr}\n```\n"
    return body


__all__ = [
    "CommandResult",
    "ToolError",
    "VALID_TARGETS",
    "format_subprocess_error",
    "remote_command_block",
    "require_binary",
    "run_subprocess",
    "validate_target",
]
