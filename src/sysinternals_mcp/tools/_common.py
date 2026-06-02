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

    NOTE: most v0.2 tools call :func:`lablink_first_remote_block`
    instead, which leads with a LabLink dispatch recommendation and
    appends a JSON sidecar an LLM can hand straight to an MCP that
    actually has remote-execution tools. This raw helper is kept for
    callers that just want the PowerShell fence without the transport
    recommendation block (e.g. tools that emit several commands in a
    sequence).
    """
    parts = [_quote(p) for p in cmdline]
    body = " ".join(parts)
    out = ["```powershell", body, "```"]
    if note:
        out.append("")
        out.append(note)
    return "\n".join(out)


def lablink_first_remote_block(
    cmdline: list[str],
    *,
    parse_with: str | None = None,
    expected_runtime_s: int = 5,
    timeout_s: int = 60,
    note: str = "",
) -> str:
    """Render a LabLink-first remote-execution markdown block.

    Sysinternals MCP has zero coupling to any specific remote-exec
    transport (no Python ``import lablink``, no env var referencing
    LabLink, no calls). This helper just *names* LabLink as the
    recommended dispatch when an LLM needs to execute the emitted
    command on another host, with PSRemoting and manual paste as
    fallbacks. The shape is deliberately stable so an LLM can:

    - read the prose "use LabLink first";
    - peel off the fenced ```json`` sidecar and pass the dict straight
      to a remote-exec MCP (``lablink.execute_command(...)``,
      ``ssh.run(...)``, etc.);
    - or just paste the ```powershell`` block manually.

    The JSON sidecar fields match the LabLink ``execute_command``
    schema (``node``, ``command``, ``shell``, ``timeout``), with the
    extra ``parse_with`` and ``expected_runtime_s`` hints the LLM can
    use to drive a follow-up parse tool. ``node`` is intentionally
    omitted -- the caller supplies it.

    Args:
        cmdline: Argv list of the command to run on the remote host.
        parse_with: Optional Sysinternals MCP tool name the caller can
            use to roundtrip the stdout (e.g. ``"parse_handle_output"``).
        expected_runtime_s: Rough hint for how long the command takes.
        timeout_s: Suggested transport timeout.
        note: Optional trailing prose appended after the JSON sidecar.
    """
    parts = [_quote(p) for p in cmdline]
    body = " ".join(parts)
    sidecar = {
        "command": body,
        "shell": "powershell",
        "timeout_s": int(timeout_s),
        "expected_runtime_s": int(expected_runtime_s),
    }
    if parse_with:
        sidecar["parse_with"] = parse_with
    json_lines = ["{"]
    items = list(sidecar.items())
    for i, (key, val) in enumerate(items):
        suffix = "," if i < len(items) - 1 else ""
        if isinstance(val, int):
            json_lines.append(f'  "{key}": {val}{suffix}')
        else:
            escaped = str(val).replace("\\", "\\\\").replace('"', '\\"')
            json_lines.append(f'  "{key}": "{escaped}"{suffix}')
    json_lines.append("}")
    json_body = "\n".join(json_lines)

    out = [
        "**Recommended dispatch:** LabLink (then PSRemoting, then manual paste).",
        "",
        "1. **LabLink (preferred)** — pass the JSON sidecar below to "
        "`lablink.execute_command(node=<your-node>, ...)`.",
        "2. **PSRemoting** — `Invoke-Command -ComputerName <host> "
        "-ScriptBlock { ... }` with the command body.",
        "3. **Manual paste** — copy the PowerShell block into a "
        "console on the target.",
        "",
        "```powershell",
        body,
        "```",
        "",
        "```json",
        json_body,
        "```",
    ]
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
    "lablink_first_remote_block",
    "remote_command_block",
    "require_binary",
    "run_subprocess",
    "validate_target",
]
