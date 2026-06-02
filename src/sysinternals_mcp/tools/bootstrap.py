"""``bootstrap_sysinternals`` MCP tool.

Headline v0.2 UX: ask the user once whether to accept the Sysinternals
EULA, then install the binaries via one of three methods (zip, winget,
live). The tool never executes anything itself; it returns PowerShell
that LabLink (or the operator) runs on the target.
"""

from __future__ import annotations

from sysinternals_mcp.app import mcp
from sysinternals_mcp.eula import is_eula_pre_accepted
from sysinternals_mcp.install import (
    DEFAULT_INSTALL_DIR,
    VALID_INSTALL_METHODS,
    build_install_script,
    consent_required_markdown,
    probe_script,
)
from sysinternals_mcp.tools._common import (
    lablink_first_remote_block,
    validate_target,
)


def _format_local_block(script: str, install_dir: str) -> str:
    """Render a local-target install instruction block."""
    return (
        "Run this PowerShell on the local machine. Requires an "
        "elevated session if `install_dir` is under "
        "`%ProgramFiles%`.\n\n"
        "```powershell\n"
        f"{script}\n"
        "```\n\n"
        f"After install, verify with `setup_sysinternals(target='local')` "
        f"or check `{install_dir}`."
    )


@mcp.tool()
def bootstrap_sysinternals(
    target: str = "local",
    install_method: str = "zip",
    install_dir: str = DEFAULT_INSTALL_DIR,
    accept_eula: bool = False,
    force: bool = False,
) -> str:
    """Install (or re-install) Sysinternals binaries on the target host.

    Args:
        target: ``"local"`` returns a PowerShell block to run here.
            ``"remote"`` returns a LabLink-first dispatch block.
        install_method: ``"zip"`` (default, single download), ``"winget"``
            (uses ``winget install Microsoft.Sysinternals``; not
            available on Server Core), or ``"live"`` (per-binary
            download from ``live.sysinternals.com``).
        install_dir: Destination folder. Defaults to ``C:\\Sysinternals``.
            For winget this argument is informational only — winget
            chooses its own install location.
        accept_eula: When ``False`` (default), this tool returns a
            CONSENT REQUIRED block asking the LLM to confirm with the
            user first. When ``True``, the install script also writes
            ``HKCU\\Software\\Sysinternals\\<Tool>\\EulaAccepted=1`` for
            every known binary. The env var
            ``SYSINTERNALS_MCP_ACCEPT_EULA=1`` overrides this to True.
        force: When ``False`` (default), the emitted script probes for
            existing binaries and skips the download if found. When
            ``True``, reinstalls unconditionally.

    Returns:
        Markdown with the install runbook. The LLM should NOT execute
        any of the commands itself — render them to the user verbatim.
    """
    err = validate_target(target)
    if err is not None:
        return err
    if install_method.lower() not in VALID_INSTALL_METHODS:
        return (
            f"**Unknown install_method `{install_method}`.** "
            f"Valid: {', '.join(VALID_INSTALL_METHODS)}."
        )

    # Three flip paths for the CONSENT REQUIRED prompt:
    # 1. accept_eula=True kwarg
    # 2. SYSINTERNALS_MCP_ACCEPT_EULA env var (is_eula_pre_accepted())
    # 3. (Implicit) the LLM previously called accept_sysinternals_eula
    #    and is now passing accept_eula=True back in.
    pre_accepted_via_env = is_eula_pre_accepted()
    effective_accept = accept_eula or pre_accepted_via_env

    sections: list[str] = []
    sections.append(
        f"**`bootstrap_sysinternals` — install_method=`{install_method}`, "
        f"install_dir=`{install_dir}`, target=`{target}`**"
    )

    if not effective_accept:
        sections.append(consent_required_markdown())
        sections.append(
            "*Re-invoke `bootstrap_sysinternals(accept_eula=True)` after "
            "the user has answered Yes. To suppress this prompt for "
            "the whole MCP server session, set "
            "`SYSINTERNALS_MCP_ACCEPT_EULA=1` in the server's "
            "environment before launch.*"
        )
        return "\n\n".join(sections) + "\n"

    if pre_accepted_via_env and not accept_eula:
        sections.append(
            "*Note: `SYSINTERNALS_MCP_ACCEPT_EULA` is set; treating "
            "`accept_eula` as True for this call.*"
        )

    script = build_install_script(install_method, install_dir, accept_eula=True)
    assert script is not None  # validated above

    if not force:
        sections.append(
            "**Skip-if-already-installed probe**\n\n"
            "```powershell\n"
            + probe_script(install_dir)
            + "```\n\n"
            "*If the probe returns 0, the install step below can be "
            "skipped. Pass `force=True` to reinstall unconditionally.*"
        )

    if target == "remote":
        sections.append("**Install step**")
        # The install script is a multi-line PowerShell program. Pass
        # it as ``script_body=`` so the helper emits it verbatim inside
        # the fenced powershell block. The older ``[script]`` argv form
        # routed through ``_quote`` which wrapped the whole body in
        # single quotes, turning it into a string literal that
        # PowerShell evaluates to itself and discards.
        sections.append(
            lablink_first_remote_block(
                script_body=script,
                parse_with="",
                expected_runtime_s=30,
                timeout_s=600,
                note=(
                    "Run the install script above on the target via "
                    "LabLink (or pasted into a remote PowerShell "
                    "session). Then call `setup_sysinternals(target="
                    "'remote')` to verify the binaries resolve."
                ),
            )
        )
    else:
        sections.append("**Install step**")
        sections.append(_format_local_block(script, install_dir))

    if install_method.lower() == "winget":
        sections.append(
            "*Winget caveat: not available on Windows Server Core "
            "editions. Fall back to `install_method='zip'` there.*"
        )

    return "\n\n".join(sections) + "\n"
