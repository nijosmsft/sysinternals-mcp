"""``sigcheck`` and ``parse_sigcheck_output`` MCP tools.

``sigcheck.exe -c -a -h`` produces CSV with signature, version, and
hash info for one or more files. This module wraps it with the
standard local/remote contract.
"""

from __future__ import annotations

import os

from sysinternals_mcp.app import mcp
from sysinternals_mcp.formatting.markdown import format_table
from sysinternals_mcp.parsing.sigcheck_parser import parse_sigcheck_csv
from sysinternals_mcp.tools._common import (
    ToolError,
    format_subprocess_error,
    remote_command_block,
    require_binary,
    run_subprocess,
    validate_target,
)

_TOOL = "sigcheck.exe"

# Subset of columns we surface in the default markdown table. Sigcheck
# returns ~16 columns; show the useful triage subset.
_DEFAULT_COLUMNS = (
    "Path",
    "Verified",
    "Publisher",
    "Company",
    "Description",
    "File Version",
    "MD5",
    "SHA256",
)


def _build_cmdline(binary: str, path: str) -> list[str]:
    return [binary, "-accepteula", "-nobanner", "-c", "-a", "-h", path]


def _render_output(text: str, path: str) -> str:
    df = parse_sigcheck_csv(text)
    if df.empty:
        return (
            f"*No sigcheck data for `{path}`.* "
            "The file may not exist or sigcheck returned only its "
            "banner. Verify the path."
        )
    available = [c for c in _DEFAULT_COLUMNS if c in df.columns]
    primary_cols = available or list(df.columns)
    return (
        f"**Sigcheck `{path}`** ({len(df):,} file(s))\n\n"
        + format_table(df, columns=primary_cols, max_rows=50)
        + "\n\n"
        f"*Columns returned by sigcheck:* "
        f"{', '.join(f'`{c}`' for c in df.columns)}.\n"
    )


@mcp.tool()
def sigcheck(path: str, target: str = "local") -> str:
    """Verify code signature + emit hashes for a file or directory.

    Args:
        path: File or directory path. Sigcheck recurses into directories
            by default with the ``-s`` flag (not enabled here -- pass
            the explicit file path you care about).
        target: ``"local"`` runs ``sigcheck.exe`` on this machine.
            ``"remote"`` returns the command line for the operator to
            run on another host -- pipe the captured stdout (CSV) back
            into ``parse_sigcheck_output``.

    Returns:
        Markdown. Shows the triage column subset by default and lists
        every column sigcheck returned for follow-up queries.
    """
    err = validate_target(target)
    if err is not None:
        return err
    if not path or not path.strip():
        return (
            "`path` must be a non-empty file or directory path "
            "(e.g. `C:\\Windows\\System32\\notepad.exe`)."
        )

    if target == "remote":
        cmdline = _build_cmdline(_TOOL, path)
        return (
            f"**`sigcheck` -- remote target** (path=`{path}`)\n"
            "\n"
            + remote_command_block(
                cmdline,
                note=(
                    "Pipe the captured stdout (CSV) into "
                    "`parse_sigcheck_output(text=...)` to get the same "
                    "markdown shape you would see for `target='local'`."
                ),
            )
            + "\n"
        )

    binary = require_binary(_TOOL)
    if isinstance(binary, str):
        return binary
    if not os.path.exists(path):
        return f"`{path}` does not exist on this machine."

    cmdline = _build_cmdline(str(binary), path)
    try:
        result = run_subprocess(cmdline, timeout=120)
    except ToolError as exc:
        return f"**`sigcheck` failed**: {exc}"

    if result.returncode != 0 and not result.stdout.strip():
        return format_subprocess_error(result, "sigcheck.exe")
    return _render_output(result.stdout, path)


@mcp.tool()
def parse_sigcheck_output(text: str) -> str:
    """Parse raw ``sigcheck.exe -c`` CSV stdout into markdown.

    Pair this with ``sigcheck(target='remote')``: run the emitted
    command on the remote host, capture stdout (CSV), then pass it
    here.
    """
    if not text or not text.strip():
        return "*Empty input.* Pass the raw CSV stdout of `sigcheck -c`."
    return _render_output(text, path="<from text>")
