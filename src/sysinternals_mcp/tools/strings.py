"""``strings`` MCP tool — extract printable strings from a binary."""

from __future__ import annotations

from sysinternals_mcp.app import mcp
from sysinternals_mcp.formatting.markdown import format_table
from sysinternals_mcp.parsing.strings_parser import parse_strings_output as _parse
from sysinternals_mcp.tools._common import (
    ToolError,
    format_subprocess_error,
    lablink_first_remote_block,
    require_binary,
    run_subprocess,
    validate_target,
)

_TOOL = "strings.exe"


def _build_cmdline(
    binary: str, path: str, min_length: int, with_offsets: bool, ascii_only: bool
) -> list[str]:
    cmd = [binary, "-accepteula", "-nobanner"]
    if min_length > 0:
        cmd += ["-n", str(min_length)]
    if with_offsets:
        cmd.append("-o")
    if ascii_only:
        cmd.append("-a")
    cmd.append(path)
    return cmd


def _render_output(text: str, path: str, filter_text: str, max_rows: int) -> str:
    df = _parse(text)
    if df.empty:
        return (
            f"*No strings parsed for `{path}`.* "
            "The file may be empty, missing, or strings.exe returned "
            "only a banner."
        )
    if filter_text:
        df = df[df["String"].str.contains(filter_text, case=False, na=False)]
        if df.empty:
            return f"*No strings in `{path}` matched filter `{filter_text}`.*"
    return (
        f"**Strings in `{path}`** "
        f"({len(df):,} rows"
        + (f", filter=`{filter_text}`" if filter_text else "")
        + ")\n\n"
        + format_table(df, max_rows=max_rows)
        + "\n"
    )


@mcp.tool()
def strings(
    target: str = "local",
    path: str = "",
    min_length: int = 8,
    with_offsets: bool = False,
    ascii_only: bool = False,
    filter: str = "",
    max_rows: int = 200,
) -> str:
    """Extract ASCII + Unicode strings from a binary.

    Args:
        target: ``"local"`` runs ``strings`` here. ``"remote"`` returns
            a LabLink-first dispatch block.
        path: Required. Path to the file to scan.
        min_length: ``-n <N>``; suppress strings shorter than ``N``.
            Default 8.
        with_offsets: ``-o``; include byte offset in output. Default off.
        ascii_only: ``-a``; ASCII only (skip Unicode). Default off.
        filter: Optional case-insensitive substring filter applied
            post-extraction to the parsed rows.
        max_rows: Maximum rows in the rendered markdown table.
            Default 200.

    Returns:
        Markdown table of extracted strings.
    """
    err = validate_target(target)
    if err is not None:
        return err
    if not path:
        return (
            "**`strings` requires `path=`.** "
            "Pass an absolute or relative path to the file."
        )

    if target == "remote":
        cmdline = _build_cmdline(
            _TOOL, path, min_length, with_offsets, ascii_only
        )
        return (
            f"**`strings` — remote target** (path=`{path}`)\n\n"
            + lablink_first_remote_block(
                cmdline,
                parse_with="parse_strings_output",
                expected_runtime_s=5,
                timeout_s=300,
                note=(
                    "Pipe captured stdout into "
                    "`parse_strings_output(text=..., path=..., filter=..., "
                    "max_rows=...)` to render the table locally."
                ),
            )
            + "\n"
        )

    binary = require_binary(_TOOL)
    if isinstance(binary, str):
        return binary
    cmdline = _build_cmdline(
        str(binary), path, min_length, with_offsets, ascii_only
    )
    try:
        result = run_subprocess(cmdline, timeout=300)
    except ToolError as exc:
        return f"**`strings` failed**: {exc}"
    if result.returncode != 0 and not result.stdout.strip():
        return format_subprocess_error(result, "strings.exe")
    return _render_output(result.stdout, path, filter, max_rows)


@mcp.tool()
def parse_strings_output(
    text: str, path: str = "<unknown>", filter: str = "", max_rows: int = 200
) -> str:
    """Parse raw ``strings`` stdout into a markdown table."""
    if not text or not text.strip():
        return "*Empty input.* Pass the raw stdout of `strings -accepteula`."
    return _render_output(text, path, filter, max_rows)
