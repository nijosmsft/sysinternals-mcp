"""``listdlls`` MCP tool — list DLLs loaded by a process or all processes."""

from __future__ import annotations

from sysinternals_mcp.app import mcp
from sysinternals_mcp.formatting.markdown import format_table
from sysinternals_mcp.parsing.listdlls_parser import (
    parse_listdlls_text,
    summarize_listdlls,
)
from sysinternals_mcp.tools._common import (
    ToolError,
    format_subprocess_error,
    lablink_first_remote_block,
    require_binary,
    run_subprocess,
    validate_target,
)

_TOOL = "listdlls.exe"


def _build_cmdline(binary: str, process: str) -> list[str]:
    cmd = [binary, "-accepteula"]
    if process and process != "*":
        cmd.append(process)
    return cmd


def _render_output(text: str, process: str) -> str:
    df = parse_listdlls_text(text)
    if df.empty:
        return (
            f"*No DLL rows parsed for `{process}`.* "
            "The process may not exist, or listdlls produced only a "
            "banner. Verify with `pslist`."
        )
    summary = summarize_listdlls(df)
    return (
        f"**DLLs loaded by `{process}`** "
        f"({len(df):,} rows, {summary['Process'].nunique()} process(es))"
        "\n\n**Per-process DLL counts**\n\n"
        + format_table(summary, max_rows=40)
        + "\n\n**First 50 DLL rows**\n\n"
        + format_table(df, max_rows=50)
        + "\n"
    )


@mcp.tool()
def listdlls(target: str = "local", process: str = "*") -> str:
    """List DLLs loaded by a process (or all processes).

    Args:
        target: ``"local"`` runs ``listdlls`` here. ``"remote"`` returns
            a LabLink-first dispatch block.
        process: A process name (``"notepad.exe"``), PID (``"3204"``),
            or ``"*"`` (default) to enumerate every process.

    Returns:
        Markdown. Per-process DLL counts plus the first 50 raw rows.
    """
    err = validate_target(target)
    if err is not None:
        return err

    if target == "remote":
        cmdline = _build_cmdline(_TOOL, process)
        return (
            f"**`listdlls` — remote target** (process=`{process}`)\n\n"
            + lablink_first_remote_block(
                cmdline,
                parse_with="parse_listdlls_output",
                expected_runtime_s=5 if process == "*" else 1,
                timeout_s=120,
                note=(
                    "Pipe captured stdout into "
                    "`parse_listdlls_output(text=..., process=...)` to "
                    "render the per-process DLL summary."
                ),
            )
            + "\n"
        )

    binary = require_binary(_TOOL)
    if isinstance(binary, str):
        return binary
    cmdline = _build_cmdline(str(binary), process)
    try:
        result = run_subprocess(cmdline, timeout=300)
    except ToolError as exc:
        return f"**`listdlls` failed**: {exc}"
    if result.returncode != 0 and not result.stdout.strip():
        return format_subprocess_error(result, "listdlls.exe")
    return _render_output(result.stdout, process)


@mcp.tool()
def parse_listdlls_output(text: str, process: str = "*") -> str:
    """Parse raw ``listdlls`` stdout into the same markdown view."""
    if not text or not text.strip():
        return "*Empty input.* Pass the raw stdout of `listdlls -accepteula`."
    return _render_output(text, process)
