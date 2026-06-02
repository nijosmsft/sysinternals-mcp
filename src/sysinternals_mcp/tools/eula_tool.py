"""``accept_sysinternals_eula`` MCP tool — standalone EULA pre-accept.

This tool emits the ``reg add`` command needed to pre-accept the
Sysinternals EULA for every known binary, under either HKCU
(``scope='user'``, no admin) or HKLM (``scope='machine'``, needs
elevation). The intent is: an LLM that has already obtained user
consent can call this once and then call other tools with
``accept_eula=True`` (or rely on the env var) without re-prompting.
"""

from __future__ import annotations

from sysinternals_mcp.app import mcp
from sysinternals_mcp.binary_locator import KNOWN_BINARIES
from sysinternals_mcp.eula import accept_command
from sysinternals_mcp.install import VALID_SCOPES
from sysinternals_mcp.tools._common import (
    lablink_first_remote_block,
    validate_target,
)


def _build_accept_script(scope: str) -> str:
    """PowerShell that runs `reg add` for every known binary."""
    lines = [f"# Pre-accept Sysinternals EULA ({scope} scope)"]
    for binary in KNOWN_BINARIES:
        lines.append(accept_command(binary, scope=scope))
    lines.append(
        f'Write-Host "EULA pre-accepted ({scope}) for '
        f'{len(KNOWN_BINARIES)} binaries"'
    )
    return "\n".join(lines)


@mcp.tool()
def accept_sysinternals_eula(
    target: str = "local", scope: str = "user"
) -> str:
    """Pre-accept the Sysinternals EULA for every known binary.

    Args:
        target: ``"local"`` returns a PowerShell block to run here.
            ``"remote"`` returns a LabLink-first dispatch block.
        scope: ``"user"`` (default) writes HKCU under the running
            account (no admin required). ``"machine"`` writes HKLM
            (requires an elevated session).

    Returns:
        Markdown with the `reg add` commands. Run this once per host /
        account to make the Sysinternals EULA dialog disappear for
        future invocations.
    """
    err = validate_target(target)
    if err is not None:
        return err
    if scope.lower() not in VALID_SCOPES:
        return (
            f"**Unknown scope `{scope}`.** "
            f"Valid: {', '.join(VALID_SCOPES)}."
        )

    script = _build_accept_script(scope.lower())
    note = (
        "After running, every Sysinternals binary will see "
        f"`EulaAccepted=1` under "
        f"`{'HKLM' if scope == 'machine' else 'HKCU'}\\Software\\Sysinternals\\<Tool>` "
        "and will suppress the EULA dialog."
    )
    if scope.lower() == "machine":
        note += " *Requires an elevated PowerShell session.*"

    sections: list[str] = []
    sections.append(
        f"**`accept_sysinternals_eula` — scope=`{scope}`, target=`{target}`**"
    )

    if target == "remote":
        sections.append(
            lablink_first_remote_block(
                script_body=script,
                parse_with="",
                expected_runtime_s=3,
                timeout_s=60,
                note=note,
            )
        )
    else:
        sections.append(
            "Run this PowerShell on the local machine.\n\n"
            "```powershell\n" + script + "\n```\n\n" + note
        )

    return "\n\n".join(sections) + "\n"
