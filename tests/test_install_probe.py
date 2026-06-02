"""Tests for the bootstrap probe script (CRITICAL 1 regression).

The probe script emitted by ``install.probe_script`` must be valid
PowerShell. The original buggy version was::

    if (Test-Path "$dir\\handle.exe" -and Test-Path "$dir\\procmon.exe") {

PowerShell parses ``-and`` as a parameter name to the first
``Test-Path`` call and aborts with a binding error. The fix is to
wrap each ``Test-Path`` call in its own parentheses so the parser
sees a Boolean expression rather than parameter-style ``-and``.

These tests assert both the textual fix is present (parens around
every ``Test-Path``) and -- when ``powershell.exe`` is on PATH --
that the script actually parses via ``[scriptblock]::Create()``.
"""

from __future__ import annotations

import re
import shutil
import subprocess

import pytest

from sysinternals_mcp.install import DEFAULT_INSTALL_DIR, probe_script


def test_probe_script_wraps_each_test_path_in_parens() -> None:
    """Every Test-Path call inside the if-condition must be parenthesized.

    Regression for the original ``-and`` parser bug: scan the script
    for any naked ``Test-Path`` that is not directly preceded by
    ``(``. If we ever drop the parens we want the test to fail loudly.
    """
    script = probe_script(DEFAULT_INSTALL_DIR)
    # Positive assertion: the parens-around-Test-Path form must appear.
    assert "((Test-Path" in script, (
        "Probe script must wrap each Test-Path call in parens; the "
        "rendered script was:\n" + script
    )
    # Every Test-Path inside the condition must be preceded by `(`.
    for match in re.finditer(r"(\S)\s*Test-Path", script):
        preceding = match.group(1)
        assert preceding == "(", (
            f"Found a Test-Path call not preceded by '(': "
            f"context='{match.group(0)}'. Full script:\n{script}"
        )


def test_probe_script_never_emits_naked_and_after_test_path() -> None:
    """``-and`` must never appear adjacent to an unparenthesized Test-Path.

    Tighter check than the previous test: scan for the exact pattern
    that triggered the original bug. The matcher looks for
    ``Test-Path <args> -and``; if it ever matches, the script is
    broken.
    """
    script = probe_script(DEFAULT_INSTALL_DIR)
    # The buggy form: Test-Path "..." -and (no closing paren).
    pattern = re.compile(r'Test-Path\s+"[^"]*"\s+-and')
    assert pattern.search(script) is None, (
        "Probe script contains the buggy 'Test-Path ... -and' shape "
        "that PowerShell mis-parses as a parameter binding:\n" + script
    )


def test_probe_script_checks_handle_and_procmon() -> None:
    """Sanity: the script must probe at least handle.exe and procmon.exe."""
    script = probe_script(DEFAULT_INSTALL_DIR)
    assert "handle.exe" in script
    assert "procmon.exe" in script


def test_probe_script_uses_install_dir_arg() -> None:
    """The supplied install_dir must be interpolated into the script."""
    script = probe_script(r"D:\custom\path")
    assert r"D:\custom\path" in script


@pytest.mark.skipif(
    shutil.which("powershell.exe") is None,
    reason="powershell.exe not on PATH; skipping live parser check",
)
def test_probe_script_parses_in_powershell() -> None:
    """Hand the script to PowerShell and ask it to validate the syntax.

    Uses ``[scriptblock]::Create($script)`` which performs a parse
    only -- it does not execute the body. A parse failure throws a
    ParseException that surfaces as a non-zero exit code with the
    error on stderr. We pass the script via stdin to avoid any
    command-line quoting trouble.
    """
    script = probe_script(DEFAULT_INSTALL_DIR)
    wrapper = (
        "$script = [Console]::In.ReadToEnd(); "
        "try { [scriptblock]::Create($script) | Out-Null; exit 0 } "
        "catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }"
    )
    proc = subprocess.run(  # noqa: S603,S607
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", wrapper],
        input=script,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, (
        "PowerShell rejected the probe script. stderr:\n"
        f"{proc.stderr}\nscript:\n{script}"
    )
