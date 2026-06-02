"""``coreinfo`` MCP tool — dump CPU topology and feature flags.

``coreinfo.exe -accepteula`` enumerates the CPU's logical-processor
maps (socket, NUMA, cache) and the long list of feature flags (VMX,
HTT, XD, NX, ...). The tool follows the standard local/remote
contract: ``"local"`` runs the binary; ``"remote"`` returns the
LabLink-first dispatch block.
"""

from __future__ import annotations

import pandas as pd

from sysinternals_mcp.app import mcp
from sysinternals_mcp.formatting.markdown import format_table
from sysinternals_mcp.parsing.coreinfo_parser import parse_coreinfo_output as _parse
from sysinternals_mcp.tools._common import (
    ToolError,
    format_subprocess_error,
    lablink_first_remote_block,
    require_binary,
    run_subprocess,
    validate_target,
)

_TOOL = "coreinfo.exe"


def _build_cmdline(binary: str) -> list[str]:
    return [binary, "-accepteula", "-nobanner"]


def _render_output(text: str) -> str:
    summary = _parse(text)
    sections: list[str] = []
    if summary.header_lines:
        sections.append(
            "**System**\n\n```text\n"
            + "\n".join(summary.header_lines[:10])
            + "\n```"
        )
    if summary.features:
        df = pd.DataFrame(summary.features)
        sections.append(
            "**Feature flags** "
            f"({sum(1 for f in summary.features if f['Supported'] == 'yes')} "
            f"supported / {len(summary.features)} total)\n\n"
            + format_table(df, max_rows=80)
        )
    if summary.topology_maps:
        df = pd.DataFrame(summary.topology_maps)
        sections.append(
            "**Topology maps** "
            f"({df['Map'].nunique()} maps, {len(df)} rows)\n\n"
            + format_table(df, max_rows=80)
        )
    if not sections:
        return (
            "*coreinfo returned no parseable sections.* The input was "
            "empty or not coreinfo text output."
        )
    return "\n\n".join(sections) + "\n"


@mcp.tool()
def coreinfo(target: str = "local") -> str:
    """Dump CPU topology + feature flags via coreinfo.

    Args:
        target: ``"local"`` runs ``coreinfo`` on this machine.
            ``"remote"`` returns a LabLink-first dispatch block.

    Returns:
        Markdown with three sections: System (banner / model), Feature
        flags (one row per VMX/HTT/etc with supported yes/no), and
        Topology maps (one row per socket/NUMA/cache mask).
    """
    err = validate_target(target)
    if err is not None:
        return err

    if target == "remote":
        cmdline = _build_cmdline(_TOOL)
        return (
            "**`coreinfo` — remote target**\n\n"
            + lablink_first_remote_block(
                cmdline,
                parse_with="parse_coreinfo_output",
                expected_runtime_s=2,
                timeout_s=30,
                note=(
                    "Pipe the captured stdout into "
                    "`parse_coreinfo_output(text=...)` to get the same "
                    "markdown shape as `target='local'`."
                ),
            )
            + "\n"
        )

    binary = require_binary(_TOOL)
    if isinstance(binary, str):
        return binary
    cmdline = _build_cmdline(str(binary))
    try:
        result = run_subprocess(cmdline, timeout=60)
    except ToolError as exc:
        return f"**`coreinfo` failed**: {exc}"
    if result.returncode != 0 and not result.stdout.strip():
        return format_subprocess_error(result, "coreinfo.exe")
    return _render_output(result.stdout)


@mcp.tool()
def parse_coreinfo_output(text: str) -> str:
    """Parse raw ``coreinfo`` stdout into the same markdown view."""
    if not text or not text.strip():
        return "*Empty input.* Pass the raw stdout of `coreinfo -accepteula`."
    return _render_output(text)
