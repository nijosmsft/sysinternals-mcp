"""``procdump`` MCP tool — capture a full memory dump of a running process.

v0.2 ships the **snapshot** mode only: ``procdump -accepteula -ma <pid|name>
<dump_path>``. The trigger-driven modes (``-e``, ``-c``, ``-h``, ``-p``)
are intentionally not exposed because they would block the MCP call for
unbounded time; an operator who needs them should drive procdump
manually with the emitted command line.
"""

from __future__ import annotations

import pandas as pd

from sysinternals_mcp.app import mcp
from sysinternals_mcp.formatting.markdown import format_table
from sysinternals_mcp.parsing.procdump_parser import parse_procdump_output as _parse
from sysinternals_mcp.tools._common import (
    ToolError,
    format_subprocess_error,
    lablink_first_remote_block,
    require_binary,
    run_subprocess,
    validate_target,
)

_TOOL = "procdump.exe"


def _build_cmdline(binary: str, process: str, dump_path: str) -> list[str]:
    return [binary, "-accepteula", "-nobanner", "-ma", process, dump_path]


def _render_output(text: str, process: str, dump_path: str) -> str:
    result = _parse(text)
    if not result.fields and not result.raw_lines:
        return (
            f"*procdump produced no parseable output for `{process}`.* "
            "Run with `target='remote'` to obtain the captured stdout."
        )
    sections: list[str] = []
    verdict = (
        "**Status: SUCCESS**" if result.success else "**Status: FAILED**"
    )
    sections.append(verdict)
    if result.fields:
        df = pd.DataFrame(result.fields)
        sections.append(
            f"**Dump details** for `{process}` → `{dump_path}`\n\n"
            + format_table(df)
        )
    if result.raw_lines:
        sections.append(
            "**Raw output**\n\n```text\n"
            + "\n".join(result.raw_lines[:20])
            + ("\n... (truncated)" if len(result.raw_lines) > 20 else "")
            + "\n```"
        )
    return "\n\n".join(sections) + "\n"


@mcp.tool()
def procdump(
    target: str = "local",
    process: str = "",
    dump_path: str = "",
) -> str:
    """Capture a full memory dump (``-ma``) of a running process.

    Args:
        target: ``"local"`` runs ``procdump`` here. ``"remote"`` returns
            a LabLink-first dispatch block.
        process: Required. A process name (``"notepad.exe"``) or PID.
        dump_path: Required. Output path. ProcDump appends a timestamp,
            so passing a folder (``"C:\\dumps"``) is fine.

    Returns:
        Markdown with status, dump-path / dump-size / elapsed seconds,
        and the raw status lines.
    """
    err = validate_target(target)
    if err is not None:
        return err
    if not process:
        return (
            "**`procdump` requires `process=`.** "
            "Pass a process name (`notepad.exe`) or PID (`1234`)."
        )
    if not dump_path:
        return (
            "**`procdump` requires `dump_path=`.** "
            "Pass an output folder (`C:\\dumps`) or filename."
        )

    if target == "remote":
        cmdline = _build_cmdline(_TOOL, process, dump_path)
        return (
            f"**`procdump` — remote target** (process=`{process}`)\n\n"
            + lablink_first_remote_block(
                cmdline,
                parse_with="parse_procdump_output",
                expected_runtime_s=10,
                timeout_s=300,
                note=(
                    "After the dump completes, pipe stdout into "
                    "`parse_procdump_output(text=..., process=..., "
                    "dump_path=...)` to verify status and surface the "
                    "dump-path / size."
                ),
            )
            + "\n"
        )

    binary = require_binary(_TOOL)
    if isinstance(binary, str):
        return binary
    cmdline = _build_cmdline(str(binary), process, dump_path)
    try:
        result = run_subprocess(cmdline, timeout=600)
    except ToolError as exc:
        return f"**`procdump` failed**: {exc}"
    # procdump can return non-zero on dump-count-reached, so check
    # combined output before falling back.
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    if result.returncode != 0 and not combined.strip():
        return format_subprocess_error(result, "procdump.exe")
    return _render_output(combined, process, dump_path)


@mcp.tool()
def parse_procdump_output(
    text: str, process: str = "", dump_path: str = ""
) -> str:
    """Parse raw ``procdump`` output into the status / dump-details view."""
    if not text or not text.strip():
        return "*Empty input.* Pass the raw stdout+stderr of `procdump -ma`."
    return _render_output(text, process or "<unknown>", dump_path or "<unknown>")
