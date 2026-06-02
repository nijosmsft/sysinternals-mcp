"""Setup / health-check tool: ``check_sysinternals_setup``.

This is the first tool an operator should call after installing the
server. It surfaces:

- Where the Sysinternals install was located (env var / PATH /
  default).
- Whether each known binary was found.
- Whether the EULA flag is set in ``HKCU`` for the running account.
- A paste-ready ``reg add`` command for each not-accepted tool.

The tool runs ``target='remote'`` by returning the equivalent PowerShell
probe commands so an operator can run the same audit on a remote
target via PSRemoting / LabLink / scp.
"""

from __future__ import annotations

import pandas as pd

from sysinternals_mcp.app import mcp
from sysinternals_mcp.binary_locator import (
    ENV_VAR,
    KNOWN_BINARIES,
    find_binary,
    search_paths,
)
from sysinternals_mcp.eula import accept_command, is_accepted, reg_path
from sysinternals_mcp.formatting.markdown import format_table

_VALID_TARGETS = ("local", "remote")
_DOWNLOAD_URL = "https://learn.microsoft.com/en-us/sysinternals/"


def _target_or_error(target: str) -> str | None:
    if target not in _VALID_TARGETS:
        return (
            f"Unknown target `{target}`. Valid: "
            f"{', '.join(_VALID_TARGETS)}. Use `local` to probe on this "
            "machine, or `remote` to get the equivalent commands for "
            "auditing another host."
        )
    return None


def _build_local_table() -> pd.DataFrame:
    rows = []
    for name in KNOWN_BINARIES:
        path = find_binary(name)
        if path is None:
            action = (
                f"Install Sysinternals (see {_DOWNLOAD_URL}) and set "
                f"`{ENV_VAR}` or place on PATH."
            )
            rows.append(
                {
                    "Tool": name,
                    "Found at": "*not found*",
                    "EULA accepted?": "n/a",
                    "Action": action,
                }
            )
            continue
        accepted = is_accepted(name)
        rows.append(
            {
                "Tool": name,
                "Found at": str(path),
                "EULA accepted?": "yes" if accepted else "no",
                "Action": "ok" if accepted else accept_command(name),
            }
        )
    return pd.DataFrame(rows)


def _build_remote_block() -> str:
    """Return PowerShell that performs the same audit on a remote box."""
    lines = ["```powershell"]
    lines.append("# Probe Sysinternals install on the remote target.")
    lines.append("$env:SYSINTERNALS_MCP_DIR = 'C:\\Sysinternals'  # adjust per host")
    lines.append("$names = @(" + ", ".join(f"'{b}'" for b in KNOWN_BINARIES) + ")")
    lines.append("foreach ($name in $names) {")
    lines.append("    $env_dir = $env:SYSINTERNALS_MCP_DIR")
    lines.append("    $found = $null")
    lines.append("    if ($env_dir -and (Test-Path (Join-Path $env_dir $name))) {")
    lines.append("        $found = Join-Path $env_dir $name")
    lines.append("    } else {")
    lines.append("        $cmd = Get-Command $name -ErrorAction SilentlyContinue")
    lines.append("        if ($cmd) { $found = $cmd.Source }")
    lines.append("    }")
    lines.append("    [PSCustomObject]@{")
    lines.append("        Tool = $name")
    lines.append("        Found = $found")
    lines.append("    }")
    lines.append("}")
    lines.append("")
    lines.append("# Probe HKCU EULA flags for the running account.")
    for name in KNOWN_BINARIES:
        path = reg_path(name)
        lines.append(
            f"Get-ItemProperty 'HKCU:\\{path}' -Name EulaAccepted "
            f"-ErrorAction SilentlyContinue | Select-Object PSPath,EulaAccepted"
        )
    lines.append("```")
    return "\n".join(lines)


@mcp.tool()
def check_sysinternals_setup(target: str = "local") -> str:
    """Audit the Sysinternals install + per-tool EULA state.

    Args:
        target: ``"local"`` (default) probes this machine and returns
            a populated table. ``"remote"`` returns paste-ready
            PowerShell that does the same probe on another host -- run
            it via PSRemoting, an MCP exec transport (LabLink etc.), or
            manually.

    Returns:
        Markdown. For ``local`` the columns are:
        ``Tool | Found at | EULA accepted? | Action``. For any
        not-accepted tool, ``Action`` contains a paste-ready
        ``reg add`` command that pre-accepts the EULA under the
        running account. For ``remote`` the output is a single fenced
        PowerShell block.
    """
    err = _target_or_error(target)
    if err is not None:
        return err

    if target == "remote":
        return (
            "**Sysinternals setup probe -- remote target**\n"
            "\n"
            "Run this PowerShell on the remote host (PSRemoting, an "
            "MCP exec transport such as LabLink, or paste into an RDP "
            "shell), then summarize the output yourself or pipe it "
            "back here as text.\n"
            "\n"
            + _build_remote_block()
            + "\n"
        )

    df = _build_local_table()
    table = format_table(df, max_rows=len(df) + 1)
    header = (
        "**Sysinternals setup -- local probe**\n"
        "\n"
        f"Install search order: {', '.join(search_paths())}\n"
        "\n"
    )
    footer = (
        "\n\n"
        "**Next steps**\n"
        "\n"
        f"- For any `Found at = *not found*` row, install the suite "
        f"from {_DOWNLOAD_URL} and set `{ENV_VAR}` to its directory.\n"
        "- For any `EULA accepted? = no` row, paste the `reg add` "
        "command from the Action column into PowerShell, then re-run "
        "`check_sysinternals_setup` to confirm.\n"
        "- The server passes `-accepteula` on every subprocess call "
        "anyway, so EULA acceptance is mostly cosmetic -- the only "
        "case it matters is when the server runs under a service "
        "account different from the interactive user.\n"
    )
    return header + table + footer
