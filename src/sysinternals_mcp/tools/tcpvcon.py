"""``tcpvcon`` MCP tool — list active TCP/UDP endpoints with owning PID.

``tcpvcon.exe -a -c -n`` is the CLI counterpart to TCPView. Each row
identifies one endpoint: protocol, owning process + PID, state,
local + remote 4-tuple. The MCP tool wraps that with the standard
local/remote contract and the v0.2 LabLink-first dispatch block for
``target='remote'``.
"""

from __future__ import annotations

from sysinternals_mcp.app import mcp
from sysinternals_mcp.formatting.markdown import format_table
from sysinternals_mcp.parsing.tcpvcon_parser import parse_tcpvcon_csv
from sysinternals_mcp.tools._common import (
    ToolError,
    format_subprocess_error,
    lablink_first_remote_block,
    require_binary,
    run_subprocess,
    validate_target,
)

_TOOL = "tcpvcon.exe"


def _build_cmdline(binary: str) -> list[str]:
    # -a all endpoints, -c CSV output, -n numeric ports (no DNS).
    return [binary, "-accepteula", "-nobanner", "-a", "-c", "-n"]


def _render_output(text: str, filter_text: str | None = None) -> str:
    df = parse_tcpvcon_csv(text)
    if df.empty:
        return (
            "*No tcpvcon endpoints parsed.* "
            "The host may have nothing listening, or the input wasn't "
            "tcpvcon CSV (run with `-c` for CSV mode)."
        )
    if filter_text:
        needle = filter_text.lower()
        mask = (
            df["Process"].str.lower().str.contains(needle, na=False)
            | df["LocalAddr"].str.lower().str.contains(needle, na=False)
            | df["RemoteAddr"].str.lower().str.contains(needle, na=False)
            | df["LocalPort"].astype(str).str.contains(needle, na=False)
            | df["RemotePort"].astype(str).str.contains(needle, na=False)
        )
        df = df[mask].reset_index(drop=True)
    proto_counts = df["Protocol"].value_counts().to_dict()
    proto_summary = ", ".join(
        f"{k}={v}" for k, v in sorted(proto_counts.items())
    )
    return (
        f"**tcpvcon endpoints** ({len(df):,} rows; {proto_summary})\n\n"
        + format_table(df, max_rows=80)
    )


@mcp.tool()
def tcpvcon(target: str = "local", filter: str = "") -> str:
    """List active TCP/UDP endpoints (TCPView CLI).

    Args:
        target: ``"local"`` runs ``tcpvcon -a -c -n`` on this machine
            (root-cause: who owns this socket?). ``"remote"`` returns
            a LabLink-first dispatch block (PowerShell + JSON sidecar)
            for execution on another host.
        filter: Optional case-insensitive substring filter applied
            after parsing. Matches against process name, addresses, or
            port numbers. Empty (default) returns every endpoint.

    Returns:
        Markdown. Columns: ``Protocol | Process | PID | State |
        LocalAddr | LocalPort | RemoteAddr | RemotePort``.
    """
    err = validate_target(target)
    if err is not None:
        return err

    if target == "remote":
        cmdline = _build_cmdline(_TOOL)
        return (
            "**`tcpvcon` — remote target** "
            f"(filter=`{filter or '<none>'}`)\n"
            "\n"
            + lablink_first_remote_block(
                cmdline,
                parse_with="parse_tcpvcon_output",
                expected_runtime_s=2,
                timeout_s=30,
                note=(
                    "Pipe the captured CSV stdout into "
                    "`parse_tcpvcon_output(text=...)` to get the same "
                    "markdown shape as `target='local'`. Apply "
                    "`filter=` on either end of the round-trip."
                ),
            )
            + "\n"
        )

    binary = require_binary(_TOOL)
    if isinstance(binary, str):
        return binary
    cmdline = _build_cmdline(str(binary))
    try:
        result = run_subprocess(cmdline, timeout=30)
    except ToolError as exc:
        return f"**`tcpvcon` failed**: {exc}"
    if result.returncode != 0 and not result.stdout.strip():
        return format_subprocess_error(result, "tcpvcon.exe")
    return _render_output(result.stdout, filter_text=filter or None)


@mcp.tool()
def parse_tcpvcon_output(text: str, filter: str = "") -> str:
    """Parse raw ``tcpvcon -c`` CSV stdout into the same markdown table.

    Pair with ``tcpvcon(target='remote')``: run the emitted command on
    the remote host, capture stdout, then pass it here.
    """
    if not text or not text.strip():
        return "*Empty input.* Pass the raw CSV stdout of `tcpvcon -a -c -n`."
    return _render_output(text, filter_text=filter or None)
