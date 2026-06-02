"""``handle_list`` and ``parse_handle_output`` MCP tools.

``handle.exe`` enumerates open handles for a process or every process.
This module wraps it with the standard local/remote contract.
"""

from __future__ import annotations

from sysinternals_mcp.app import mcp
from sysinternals_mcp.formatting.markdown import format_table
from sysinternals_mcp.parsing.handle_parser import (
    parse_handle_text,
    summarize_handles,
)
from sysinternals_mcp.tools._common import (
    ToolError,
    format_subprocess_error,
    remote_command_block,
    require_binary,
    run_subprocess,
    validate_target,
)

_TOOL = "handle.exe"


def _build_cmdline(binary: str, process: str) -> list[str]:
    cmd = [binary, "-accepteula", "-nobanner"]
    if process and process != "*":
        cmd += ["-p", process]
    return cmd


def _render_output(text: str, process: str) -> str:
    df = parse_handle_text(text)
    if df.empty:
        return (
            f"*No handles found for `{process}`.* "
            "The process may not exist, or `handle.exe` may have "
            "returned only its banner. Verify with `pslist`."
        )
    summary = summarize_handles(df)
    return (
        f"**Handles for `{process}`** "
        f"({len(df):,} rows, "
        f"{summary['Process'].nunique()} process(es))\n\n"
        "**Per-(process, type) summary**\n\n"
        + format_table(summary)
        + "\n\n**First 50 handle rows**\n\n"
        + format_table(df, max_rows=50)
    )


@mcp.tool()
def handle_list(process: str = "*", target: str = "local") -> str:
    """List open handles for a process (or every process).

    Args:
        process: Process name or PID. ``"*"`` (default) lists every
            process. Examples: ``"chrome"``, ``"1234"``,
            ``"explorer.exe"``.
        target: ``"local"`` runs ``handle.exe`` on this machine and
            returns parsed markdown. ``"remote"`` returns the exact
            command line as a fenced ```powershell``` block for the
            operator to run on another host -- pipe the captured
            stdout back into ``parse_handle_output``.

    Returns:
        Markdown. For ``local``: a summary table grouped by process
        and handle type, followed by the first 50 handle rows. For
        ``remote``: a single fenced PowerShell block.
    """
    err = validate_target(target)
    if err is not None:
        return err

    if target == "remote":
        cmdline = _build_cmdline(_TOOL, process)  # use bare exe name
        return (
            f"**`handle_list` -- remote target** (process=`{process}`)\n"
            "\n"
            + remote_command_block(
                cmdline,
                note=(
                    "Pipe the captured stdout into "
                    "`parse_handle_output(text=...)` to get the same "
                    "markdown shape you would see for `target='local'`."
                ),
            )
            + "\n"
        )

    binary = require_binary(_TOOL)
    if isinstance(binary, str):
        return binary

    cmdline = _build_cmdline(str(binary), process)
    try:
        result = run_subprocess(cmdline)
    except ToolError as exc:
        return f"**`handle_list` failed**: {exc}"

    if result.returncode != 0 and not result.stdout.strip():
        return format_subprocess_error(result, "handle.exe")
    return _render_output(result.stdout, process)


@mcp.tool()
def parse_handle_output(text: str) -> str:
    """Parse the raw stdout of ``handle.exe`` into the same markdown shape.

    Pair this with ``handle_list(target='remote')``: run the emitted
    command on the remote host via your transport of choice, then pass
    the captured stdout into this tool.

    Args:
        text: Raw stdout from ``handle.exe``. The banner is tolerated
            and ignored.
    """
    if not text or not text.strip():
        return "*Empty input.* Pass the raw stdout of `handle.exe`."
    return _render_output(text, process="<from text>")
