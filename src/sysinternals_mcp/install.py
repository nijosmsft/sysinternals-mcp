"""Bootstrap installer for Sysinternals binaries.

v0.2 ships three install methods (operator picks via ``install_method``):

- ``"zip"`` (default): Download the Sysinternals Suite zip from
  ``https://download.sysinternals.com/files/SysinternalsSuite.zip`` and
  expand it under the requested directory. ARM64 hosts get the
  ``SysinternalsSuite-ARM64.zip`` variant. Single HTTP call, no admin
  required when installing under the user's profile.
- ``"winget"``: ``winget install --id Microsoft.Sysinternals``. Cleanest
  when winget is available; Windows Server Core editions ship without
  it.
- ``"live"``: Per-binary download from ``https://live.sysinternals.com``.
  Cheapest for "I just need handle.exe and pslist.exe"; verbose for
  full suite installs.

The CONSENT REQUIRED markdown block (see :func:`consent_required_markdown`)
is rendered unless one of three flip paths is active:

1. ``accept_eula=True`` argument on the calling tool.
2. ``SYSINTERNALS_MCP_ACCEPT_EULA`` env var (see :mod:`eula`).
3. Standalone ``accept_sysinternals_eula`` tool was previously invoked.

This module emits PowerShell commands and runbook text; it never
executes anything itself (the remote-execution transport or operator
handles that).
"""

from __future__ import annotations

from sysinternals_mcp.binary_locator import KNOWN_BINARIES

DEFAULT_INSTALL_DIR = r"C:\Sysinternals"
SUITE_ZIP_URL = "https://download.sysinternals.com/files/SysinternalsSuite.zip"
SUITE_ZIP_URL_ARM64 = (
    "https://download.sysinternals.com/files/SysinternalsSuite-ARM64.zip"
)
LIVE_BASE_URL = "https://live.sysinternals.com"
WINGET_PACKAGE_ID = "Microsoft.Sysinternals"
EULA_URL = (
    "https://learn.microsoft.com/en-us/sysinternals/license-terms"
)


def consent_required_markdown() -> str:
    """Return the CONSENT REQUIRED prompt the LLM must show the user.

    The text is structured so the LLM reads it naturally and prompts
    the user for a Yes/No-but-install/Skip choice. Wording is verbatim
    per the bootstrap UX spec.
    """
    return (
        "**CONSENT REQUIRED — Sysinternals Software License Terms**\n\n"
        "Sysinternals tools are governed by the Microsoft Sysinternals "
        "Software License Terms. By proceeding, the user agrees to those "
        "terms on behalf of every account that runs these tools on this "
        "host. Each binary writes "
        "`HKCU\\Software\\Sysinternals\\<Tool>\\EulaAccepted=1` after "
        "its first `-accepteula` invocation so the dialog never appears.\n\n"
        f"Full text: <{EULA_URL}>\n\n"
        "**Please ask the user which of these three responses applies, "
        "and do not proceed until they answer:**\n\n"
        "| Option | What it does |\n"
        "| --- | --- |\n"
        "| **Yes** | Install Sysinternals and pre-accept the EULA "
        "for every binary now. |\n"
        "| **No-but-install** | Install the binaries but leave the EULA "
        "dialog enabled (the user will see it the first time each "
        "tool runs interactively). |\n"
        "| **Skip-future-prompts** | Set the "
        "`SYSINTERNALS_MCP_ACCEPT_EULA=1` env var on the MCP server so "
        "this prompt never appears again in this session. |\n\n"
        "Once the user answers, re-invoke `bootstrap_sysinternals` "
        "with `accept_eula=True` (Yes), `accept_eula=False` "
        "(No-but-install), or first invoke "
        "`accept_sysinternals_eula(scope='user')` and then retry "
        "(Skip-future-prompts).\n"
    )


def _accepteula_block(install_dir: str) -> str:
    """Emit PowerShell that runs each binary with -accepteula once.

    Each invocation writes the HKCU EulaAccepted=1 flag for that
    binary's Sysinternals subkey. We use Start-Process with
    -WindowStyle Hidden to avoid GUI dialogs on the few binaries
    (autoruns, procmon) that still pop one even with -accepteula.
    """
    lines: list[str] = []
    lines.append(f"$dir = '{install_dir}'")
    for binary in KNOWN_BINARIES:
        lines.append(
            f"Start-Process -FilePath \"$dir\\{binary}\" "
            f"-ArgumentList '-accepteula' -WindowStyle Hidden "
            f"-Wait -ErrorAction SilentlyContinue"
        )
    return "\n".join(lines)


def _build_zip_script(install_dir: str, accept_eula: bool) -> str:
    """PowerShell that downloads + expands the suite zip."""
    script = f"""$installDir = '{install_dir}'
$arch = $env:PROCESSOR_ARCHITECTURE
if ($arch -eq 'ARM64') {{
    $zipUrl = '{SUITE_ZIP_URL_ARM64}'
}} else {{
    $zipUrl = '{SUITE_ZIP_URL}'
}}
$zipPath = Join-Path $env:TEMP 'SysinternalsSuite.zip'
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
Expand-Archive -Path $zipPath -DestinationPath $installDir -Force
Remove-Item $zipPath -ErrorAction SilentlyContinue
Write-Host "Sysinternals Suite installed to $installDir"
"""
    if accept_eula:
        script += "\n# Pre-accept the EULA for every known binary\n"
        script += _accepteula_block(install_dir) + "\n"
        script += 'Write-Host "EULA pre-accepted for all binaries"\n'
    return script


def _build_winget_script(install_dir: str, accept_eula: bool) -> str:
    """PowerShell using winget. install_dir is informational only."""
    script = f"""# winget install --id {WINGET_PACKAGE_ID} -e --accept-package-agreements --accept-source-agreements
# Winget will install to its own location (usually under
# %USERPROFILE%\\AppData\\Local\\Microsoft\\WinGet\\Packages\\). The
# install_dir argument (`{install_dir}`) is recorded here for parity
# with the zip path but is NOT used by winget.
winget install --id {WINGET_PACKAGE_ID} -e --accept-package-agreements --accept-source-agreements
"""
    if accept_eula:
        script += (
            "\n# Resolve the winget install location and pre-accept the "
            "EULA:\n"
            "$wingetDir = (winget list --id "
            f"{WINGET_PACKAGE_ID} --exact 2>$null | "
            "Select-String 'Sysinternals' | Select-Object -First 1)\n"
            "# Caveat: Windows Server Core does NOT ship winget. Use "
            "install_method='zip' on Server Core.\n"
            f"{_accepteula_block(install_dir)}\n"
        )
    return script


def _build_live_script(install_dir: str, accept_eula: bool) -> str:
    """PowerShell that pulls each binary from live.sysinternals.com."""
    binaries_arr = ", ".join(f"'{b}'" for b in KNOWN_BINARIES)
    script = f"""$installDir = '{install_dir}'
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
$binaries = @({binaries_arr})
foreach ($b in $binaries) {{
    $url = '{LIVE_BASE_URL}/' + $b
    $dest = Join-Path $installDir $b
    Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
}}
Write-Host "Sysinternals binaries pulled from live.sysinternals.com to $installDir"
"""
    if accept_eula:
        script += "\n" + _accepteula_block(install_dir) + "\n"
        script += 'Write-Host "EULA pre-accepted for all binaries"\n'
    return script


def build_install_script(
    install_method: str, install_dir: str, accept_eula: bool
) -> str | None:
    """Dispatch to the per-method script builder.

    Returns ``None`` if ``install_method`` is unknown.
    """
    method = install_method.lower()
    if method == "zip":
        return _build_zip_script(install_dir, accept_eula)
    if method == "winget":
        return _build_winget_script(install_dir, accept_eula)
    if method == "live":
        return _build_live_script(install_dir, accept_eula)
    return None


def probe_script(install_dir: str) -> str:
    """Emit PowerShell that checks whether the suite is already installed.

    Returns 0 (suite present) or 1 (not present). Used by
    bootstrap_sysinternals(force=False) to skip the install when
    binaries already exist.
    """
    return f"""$dir = '{install_dir}'
if (Test-Path "$dir\\handle.exe" -and Test-Path "$dir\\procmon.exe") {{
    Write-Host "Sysinternals already installed under $dir"
    exit 0
}} else {{
    Write-Host "Not installed"
    exit 1
}}
"""


VALID_INSTALL_METHODS = ("zip", "winget", "live")
VALID_SCOPES = ("user", "machine")


__all__ = [
    "DEFAULT_INSTALL_DIR",
    "EULA_URL",
    "LIVE_BASE_URL",
    "SUITE_ZIP_URL",
    "SUITE_ZIP_URL_ARM64",
    "VALID_INSTALL_METHODS",
    "VALID_SCOPES",
    "WINGET_PACKAGE_ID",
    "build_install_script",
    "consent_required_markdown",
    "probe_script",
]
