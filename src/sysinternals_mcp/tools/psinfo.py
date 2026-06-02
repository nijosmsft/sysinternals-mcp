"""``psinfo`` MCP tool — dump OS / hardware metadata.

Wraps ``psinfo.exe -d -s -h`` (disks, software, hotfixes) for a
comprehensive snapshot of the host. The MCP tool follows the standard
local/remote contract.
"""

from __future__ import annotations

import pandas as pd

from sysinternals_mcp.app import mcp
from sysinternals_mcp.formatting.markdown import format_table
from sysinternals_mcp.parsing.psinfo_parser import parse_psinfo_output as _parse
from sysinternals_mcp.tools._common import (
    ToolError,
    format_subprocess_error,
    lablink_first_remote_block,
    require_binary,
    run_subprocess,
    validate_target,
)

_TOOL = "psinfo.exe"


def _build_cmdline(binary: str, full: bool) -> list[str]:
    cmd = [binary, "-accepteula", "-nobanner"]
    if full:
        cmd.extend(["-d", "-s", "-h"])
    return cmd


def _render_output(text: str) -> str:
    summary = _parse(text)
    sections: list[str] = []
    if summary.fields:
        df = pd.DataFrame(summary.fields)
        sections.append(
            f"**System info** ({len(df)} fields)\n\n"
            + format_table(df, max_rows=60)
        )
    for name, lines in summary.sections.items():
        if not lines:
            continue
        sections.append(
            f"**{name}** ({len(lines)} entries)\n\n"
            + "```text\n"
            + "\n".join(lines[:40])
            + ("\n... (truncated)\n" if len(lines) > 40 else "\n")
            + "```"
        )
    if not sections:
        return (
            "*psinfo returned no parseable fields.* "
            "The input was empty or not a psinfo banner + key/value "
            "block."
        )
    return "\n\n".join(sections) + "\n"


@mcp.tool()
def psinfo(target: str = "local", full: bool = True) -> str:
    """Dump OS / hardware metadata for the host.

    Args:
        target: ``"local"`` runs ``psinfo`` here. ``"remote"`` returns
            a LabLink-first dispatch block.
        full: When ``True`` (default), passes ``-d -s -h`` to also dump
            disk volumes, installed software, and hotfixes. Set to
            ``False`` for a fast, system-only snapshot.

    Returns:
        Markdown. A System-info key/value table plus optional Disk /
        Software / Hotfixes sections.
    """
    err = validate_target(target)
    if err is not None:
        return err

    if target == "remote":
        cmdline = _build_cmdline(_TOOL, full=full)
        return (
            f"**`psinfo` — remote target** (full={full})\n\n"
            + lablink_first_remote_block(
                cmdline,
                parse_with="parse_psinfo_output",
                expected_runtime_s=8 if full else 2,
                timeout_s=60,
                note=(
                    "Pipe captured stdout into "
                    "`parse_psinfo_output(text=...)` to get the same "
                    "markdown shape as `target='local'`. `full=True` "
                    "includes disks / software / hotfixes."
                ),
            )
            + "\n"
        )

    binary = require_binary(_TOOL)
    if isinstance(binary, str):
        return binary
    cmdline = _build_cmdline(str(binary), full=full)
    try:
        result = run_subprocess(cmdline, timeout=180)
    except ToolError as exc:
        return f"**`psinfo` failed**: {exc}"
    if result.returncode != 0 and not result.stdout.strip():
        return format_subprocess_error(result, "psinfo.exe")
    return _render_output(result.stdout)


@mcp.tool()
def parse_psinfo_output(text: str) -> str:
    """Parse raw ``psinfo`` stdout into the same markdown view."""
    if not text or not text.strip():
        return "*Empty input.* Pass the raw stdout of `psinfo -d -s -h`."
    return _render_output(text)
