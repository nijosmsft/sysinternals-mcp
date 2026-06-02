"""``autoruns`` MCP tool — list every autostart entry on a Windows host.

Wraps ``autorunsc.exe`` with ``-a *`` (all categories), ``-c`` (CSV),
``-s`` (verify signatures), ``-h *`` (compute hashes). The output is a
wide table that triages every place malware (or installers) can hook
to run at boot / logon. The MCP tool exposes a default triage subset
plus a filter substring and a category restriction.
"""

from __future__ import annotations

from sysinternals_mcp.app import mcp
from sysinternals_mcp.formatting.markdown import format_table
from sysinternals_mcp.parsing.autorunsc_parser import parse_autorunsc_output as _parse
from sysinternals_mcp.tools._common import (
    ToolError,
    format_subprocess_error,
    lablink_first_remote_block,
    require_binary,
    run_subprocess,
    validate_target,
)

_TOOL = "autorunsc.exe"

# Default triage subset — full set has ~17 columns; show the ones an
# analyst usually reads first.
_DEFAULT_COLUMNS = (
    "Entry Location",
    "Entry",
    "Enabled",
    "Category",
    "Signer",
    "Image Path",
    "Launch String",
)


def _build_cmdline(binary: str, category: str | None = None) -> list[str]:
    # -ct emits tab-separated output (more robust than CSV for paths
    # with commas), -a * lists all categories, -s verifies signatures,
    # -h * hashes the image file.
    cmd = [binary, "-accepteula", "-nobanner", "-ct", "-s", "-h", "*"]
    if category and category.strip():
        cmd[-3:-3] = ["-a", category.strip()]
    else:
        cmd[-3:-3] = ["-a", "*"]
    return cmd


def _render_output(
    text: str,
    filter_text: str | None = None,
    columns: tuple[str, ...] = _DEFAULT_COLUMNS,
) -> str:
    df = _parse(text)
    if df.empty:
        return (
            "*No autorunsc entries parsed.* The input wasn't an "
            "autorunsc TSV/CSV header, or autorunsc returned only its "
            "banner."
        )
    if filter_text:
        needle = filter_text.lower()
        mask = pd.Series([False] * len(df))
        for col in df.columns:
            mask = mask | df[col].astype(str).str.lower().str.contains(
                needle, na=False
            )
        df = df[mask].reset_index(drop=True)
    if df.empty:
        return (
            f"*No autorunsc entries matched filter `{filter_text}`.* "
            f"The full table had rows but none matched."
        )
    available = [c for c in columns if c in df.columns]
    show_cols = available or list(df.columns)
    return (
        f"**Autoruns** ({len(df):,} entries)\n\n"
        + format_table(df, columns=show_cols, max_rows=80)
        + "\n\n"
        f"*Full column set:* {', '.join(f'`{c}`' for c in df.columns)}.\n"
    )


@mcp.tool()
def autoruns(
    target: str = "local",
    category: str = "",
    filter: str = "",
) -> str:
    """List every autostart entry (logon, services, drivers, ...).

    Args:
        target: ``"local"`` runs ``autorunsc`` on this machine and
            returns a parsed table. ``"remote"`` returns the
            LabLink-first dispatch block (PowerShell + JSON sidecar).
        category: Optional autorunsc category filter to restrict at
            the CLI level (faster than parsing the full set). Common
            values: ``"*"`` (all, default), ``"l"`` (logon), ``"s"``
            (services), ``"d"`` (drivers), ``"t"`` (scheduled tasks),
            ``"e"`` (Explorer add-ons), ``"i"`` (Internet Explorer).
        filter: Optional case-insensitive substring filter applied
            after parsing. Matches against any column.

    Returns:
        Markdown. Default columns: ``Entry Location | Entry | Enabled
        | Category | Signer | Image Path | Launch String``. Full
        column list listed at the end so follow-up queries know what
        to ask for.
    """
    err = validate_target(target)
    if err is not None:
        return err

    if target == "remote":
        cmdline = _build_cmdline(_TOOL, category=category)
        return (
            "**`autoruns` — remote target** "
            f"(category=`{category or '*'}`, filter=`{filter or '<none>'}`)\n"
            "\n"
            + lablink_first_remote_block(
                cmdline,
                parse_with="parse_autoruns_output",
                expected_runtime_s=15,
                timeout_s=120,
                note=(
                    "autorunsc can take 5-15 seconds because it walks "
                    "~17 categories and verifies signatures. Pipe the "
                    "captured TSV stdout into "
                    "`parse_autoruns_output(text=...)` to get the same "
                    "markdown shape as `target='local'`."
                ),
            )
            + "\n"
        )

    binary = require_binary(_TOOL)
    if isinstance(binary, str):
        return binary
    cmdline = _build_cmdline(str(binary), category=category)
    try:
        result = run_subprocess(cmdline, timeout=180)
    except ToolError as exc:
        return f"**`autoruns` failed**: {exc}"
    if result.returncode != 0 and not result.stdout.strip():
        return format_subprocess_error(result, "autorunsc.exe")
    return _render_output(result.stdout, filter_text=filter or None)


@mcp.tool()
def parse_autoruns_output(text: str, filter: str = "") -> str:
    """Parse raw ``autorunsc -ct`` TSV stdout into the same markdown table."""
    if not text or not text.strip():
        return "*Empty input.* Pass the raw TSV/CSV stdout of `autorunsc -ct -s -h * -a *`."
    return _render_output(text, filter_text=filter or None)


# Pandas is only needed for the per-column mask construction. Import
# lazily so the module's top-level cost stays low.
import pandas as pd  # noqa: E402
