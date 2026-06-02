"""``pslist`` and ``parse_pslist_output`` MCP tools."""

from __future__ import annotations

from sysinternals_mcp.app import mcp
from sysinternals_mcp.formatting.markdown import format_table
from sysinternals_mcp.parsing.pslist_parser import apply_filter, parse_pslist_text
from sysinternals_mcp.tools._common import (
    ToolError,
    format_subprocess_error,
    lablink_first_remote_block,
    require_binary,
    run_subprocess,
    validate_target,
)

_TOOL = "pslist.exe"


def _build_cmdline(binary: str) -> list[str]:
    return [binary, "-accepteula", "-nobanner"]


def _render_output(text: str, filter_str: str) -> str:
    df = parse_pslist_text(text)
    if df.empty:
        return (
            "*No processes parsed from pslist output.* "
            "The output may be truncated or in an unexpected format."
        )
    filtered = apply_filter(df, filter_str)
    if filter_str and filtered.empty:
        return (
            f"*No processes matched filter `{filter_str}`.* "
            f"({len(df):,} total processes parsed.)"
        )
    header = (
        f"**Processes** ({len(filtered):,} of {len(df):,} shown"
        + (f", filter=`{filter_str}`" if filter_str else "")
        + ")\n\n"
    )
    return header + format_table(filtered, max_rows=200)


@mcp.tool()
def pslist(filter: str = "", target: str = "local") -> str:
    """List running processes via ``pslist.exe``.

    Args:
        filter: Optional case-insensitive substring filter on process
            name (e.g. ``"chrome"``). Empty (default) returns every
            process.
        target: ``"local"`` runs the binary on this machine.
            ``"remote"`` returns the command line for the operator to
            run on another host -- pipe the captured stdout back into
            ``parse_pslist_output``.
    """
    err = validate_target(target)
    if err is not None:
        return err

    if target == "remote":
        cmdline = _build_cmdline(_TOOL)
        return (
            f"**`pslist` -- remote target** (filter=`{filter}`)\n"
            "\n"
            + lablink_first_remote_block(
                cmdline,
                parse_with="parse_pslist_output",
                expected_runtime_s=2,
                timeout_s=30,
                note=(
                    "Pipe the captured stdout into "
                    "`parse_pslist_output(text=...)`. The `filter` arg "
                    "is applied client-side on the parsed table, so "
                    "you can also leave the remote command unfiltered "
                    "and filter via the parse tool."
                ),
            )
            + "\n"
        )

    binary = require_binary(_TOOL)
    if isinstance(binary, str):
        return binary

    cmdline = _build_cmdline(str(binary))
    try:
        result = run_subprocess(cmdline)
    except ToolError as exc:
        return f"**`pslist` failed**: {exc}"

    if result.returncode != 0 and not result.stdout.strip():
        return format_subprocess_error(result, "pslist.exe")
    return _render_output(result.stdout, filter)


@mcp.tool()
def parse_pslist_output(text: str, filter: str = "") -> str:
    """Parse raw ``pslist.exe`` stdout into the same markdown shape.

    Args:
        text: Raw stdout captured from a remote pslist invocation.
        filter: Optional case-insensitive name substring filter.
    """
    if not text or not text.strip():
        return "*Empty input.* Pass the raw stdout of `pslist.exe`."
    return _render_output(text, filter)
