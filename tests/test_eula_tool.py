"""Tests for ``sysinternals_mcp.tools.eula_tool``.

Covers two regressions:

- CRITICAL 3: ``accept_sysinternals_eula(target="remote", ...)`` was
  passing a multi-line PowerShell script as a single argv element to
  ``lablink_first_remote_block``. The helper quote-wrapped it,
  rendering a string literal that does nothing when pasted.
- IMPORTANT 4: ``scope`` case-sensitivity. ``scope='Machine'`` (or any
  non-lowercase variant) would lower it for the registry-write logic
  but NOT for the inline ``'HKLM' if scope == 'machine' else 'HKCU'``
  expression in the note text, so the rendered note reported the
  wrong hive.
"""

from __future__ import annotations

import json
import re

import pytest

from sysinternals_mcp.tools.eula_tool import accept_sysinternals_eula


# ---------- CRITICAL 3: rendered script is not quote-wrapped ----------


def test_accept_eula_remote_script_is_not_quote_wrapped() -> None:
    out = accept_sysinternals_eula(target="remote", scope="user")
    ps_blocks = re.findall(r"```powershell\n(.*?)\n```", out, re.DOTALL)
    json_blocks = re.findall(r"```json\n(.*?)\n```", out, re.DOTALL)
    assert len(ps_blocks) == 1, (
        f"expected exactly one ```powershell fence; got "
        f"{len(ps_blocks)}\nout:\n{out}"
    )
    assert len(json_blocks) == 1
    body = ps_blocks[0]
    sidecar = json.loads(json_blocks[0])

    # The script must NOT start with a single quote (would be a
    # PowerShell string literal that evaluates and is discarded).
    assert not body.startswith("'"), (
        "accept-eula script is quote-wrapped; powershell block "
        f"starts with a single quote. Block:\n{body}"
    )
    # The script begins with the section comment ``# Pre-accept ...``.
    assert body.lstrip().startswith("# Pre-accept"), (
        "accept-eula script does not begin with the # Pre-accept "
        f"header. Block:\n{body}"
    )
    # ``reg add`` should appear as a top-level command on its own line.
    assert re.search(r"^reg add ", body, re.MULTILINE), (
        "accept-eula script does not contain ``reg add`` as a "
        f"top-level command. Block:\n{body}"
    )
    # Sidecar ``command`` equals the rendered powershell block.
    assert sidecar["command"] == body


# ---------- IMPORTANT 4: scope case-sensitivity ----------


@pytest.mark.parametrize("scope", ["user", "User", "USER"])
def test_accept_eula_user_scope_writes_hkcu_consistently(scope: str) -> None:
    """User scope (in any case) must write HKCU AND say HKCU in note text."""
    out = accept_sysinternals_eula(target="local", scope=scope)
    # The reg-add script must target HKCU.
    assert "HKCU" in out, f"scope={scope!r}: HKCU missing from output"
    # And must NOT slip an HKLM reference in (no rogue HKLM in note).
    assert "HKLM" not in out, (
        f"scope={scope!r}: rogue HKLM mention with user scope:\n{out}"
    )


@pytest.mark.parametrize("scope", ["machine", "Machine", "MACHINE"])
def test_accept_eula_machine_scope_writes_hklm_consistently(scope: str) -> None:
    """Machine scope (in any case) must write HKLM AND say HKLM in note text."""
    out = accept_sysinternals_eula(target="local", scope=scope)
    # Reg-add script targets HKLM.
    assert "HKLM" in out, f"scope={scope!r}: HKLM missing from output"
    # The note must NOT say "HKCU" anywhere (that was the bug -- the
    # note text used a case-sensitive comparison and would read
    # ``HKCU`` for ``scope='Machine'`` despite the reg-add command
    # writing to HKLM).
    assert "HKCU" not in out, (
        f"scope={scope!r}: rogue HKCU mention with machine scope -- "
        f"the IMPORTANT 4 case-sensitivity bug is back:\n{out}"
    )
    # Elevation note must be present for machine scope.
    assert "elevated" in out.lower(), (
        f"scope={scope!r}: missing elevation requirement note"
    )


def test_accept_eula_remote_machine_scope_consistently_references_hklm() -> None:
    """Same IMPORTANT 4 check but for the remote dispatch surface."""
    out = accept_sysinternals_eula(target="remote", scope="Machine")
    assert "HKLM" in out
    assert "HKCU" not in out


# ---------- existing validation paths ----------


def test_accept_eula_rejects_unknown_scope() -> None:
    out = accept_sysinternals_eula(target="local", scope="bogus")
    assert "Unknown scope" in out


def test_accept_eula_rejects_unknown_target() -> None:
    out = accept_sysinternals_eula(target="cluster", scope="user")
    assert "Unknown target" in out
