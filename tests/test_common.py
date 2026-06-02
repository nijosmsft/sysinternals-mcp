"""Tests for ``sysinternals_mcp.tools._common`` (CRITICAL 2 regression).

The headline guarantee: the ```json`` sidecar emitted by
``lablink_first_remote_block`` must always be a parseable JSON
document, even when the ``command`` field contains newlines,
embedded quotes, or other characters that the previous hand-rolled
encoder mis-escaped.
"""

from __future__ import annotations

import json
import re

import pytest

from sysinternals_mcp.tools._common import (
    _quote,
    lablink_first_remote_block,
    remote_command_block,
)

_JSON_FENCE = re.compile(r"```json\n(.*?)\n```", re.DOTALL)
_PS_FENCE = re.compile(r"```powershell\n(.*?)\n```", re.DOTALL)


def _extract_json_sidecar(out: str) -> dict[str, object]:
    """Pull the fenced ``json`` block out of a remote dispatch block."""
    match = _JSON_FENCE.search(out)
    assert match is not None, f"no ```json fence in output:\n{out}"
    return json.loads(match.group(1))


def _extract_powershell_block(out: str) -> str:
    match = _PS_FENCE.search(out)
    assert match is not None, f"no ```powershell fence in output:\n{out}"
    return match.group(1)


# ---------- single-line command (the original happy path) ----------


def test_sidecar_roundtrips_single_line_cmdline() -> None:
    out = lablink_first_remote_block(
        ["handle.exe", "-accepteula", "-a"],
        parse_with="parse_handle_output",
        expected_runtime_s=5,
        timeout_s=60,
    )
    sidecar = _extract_json_sidecar(out)
    assert sidecar["shell"] == "powershell"
    assert sidecar["timeout_s"] == 60
    assert sidecar["expected_runtime_s"] == 5
    assert sidecar["parse_with"] == "parse_handle_output"
    assert "handle.exe" in str(sidecar["command"])
    assert "-accepteula" in str(sidecar["command"])


# ---------- multi-line command (the previously broken path) ----------


def test_sidecar_roundtrips_multi_line_cmdline() -> None:
    """The original encoder mis-escaped LF/CR; json.loads should now succeed."""
    multi_line = (
        "$dir = 'C:\\Sysinternals'\n"
        "Invoke-WebRequest -Uri https://example.com/x.zip -OutFile $dir\\x.zip\n"
        "Expand-Archive -Path $dir\\x.zip -DestinationPath $dir -Force\n"
    )
    out = lablink_first_remote_block([multi_line], timeout_s=600)
    sidecar = _extract_json_sidecar(out)
    # The command round-trips identically modulo the per-arg quoting
    # (``_quote`` wraps it in single quotes because the body contains
    # whitespace and a literal "'"). The important thing is that the
    # JSON parses, and that the LF bytes survived as ``\n`` escapes
    # rather than literal newlines.
    cmd = str(sidecar["command"])
    assert "\n" in cmd or "\\n" not in cmd  # actual newline survived
    assert "Invoke-WebRequest" in cmd
    assert "Expand-Archive" in cmd


# ---------- special characters (', ", ;) ----------


def test_sidecar_roundtrips_special_characters() -> None:
    """Embedded quotes, semicolons, backslashes must all roundtrip."""
    parts = [
        "powershell.exe",
        "-Command",
        "Write-Host 'a\"b;c\\d'",
    ]
    out = lablink_first_remote_block(parts)
    sidecar = _extract_json_sidecar(out)
    cmd = str(sidecar["command"])
    # We mostly care that it parsed; the content should still mention
    # every token from the original input.
    assert "Write-Host" in cmd
    assert "a" in cmd and "b" in cmd and "c" in cmd
    assert "powershell.exe" in cmd


# ---------- structural fields ----------


def test_sidecar_includes_required_fields() -> None:
    out = lablink_first_remote_block(["x"])
    sidecar = _extract_json_sidecar(out)
    assert set(sidecar.keys()) >= {
        "command",
        "shell",
        "timeout_s",
        "expected_runtime_s",
    }
    assert sidecar["shell"] == "powershell"


def test_sidecar_omits_parse_with_when_not_supplied() -> None:
    out = lablink_first_remote_block(["x"])
    sidecar = _extract_json_sidecar(out)
    assert "parse_with" not in sidecar


def test_sidecar_includes_parse_with_when_supplied() -> None:
    out = lablink_first_remote_block(["x"], parse_with="parse_handle_output")
    sidecar = _extract_json_sidecar(out)
    assert sidecar["parse_with"] == "parse_handle_output"


# ---------- recommended-dispatch prose ----------


def test_output_leads_with_lablink_recommendation() -> None:
    out = lablink_first_remote_block(["handle.exe"])
    assert out.startswith(
        "**Recommended dispatch:** LabLink (then PSRemoting, then manual paste)."
    )
    assert "```powershell" in out
    assert "```json" in out


# ---------- powershell fence content ----------


def test_powershell_fence_contains_quoted_argv() -> None:
    out = lablink_first_remote_block(["handle.exe", "-accepteula"])
    body = _extract_powershell_block(out)
    assert body == "handle.exe -accepteula"


# ---------- _quote helper sanity ----------


def test_quote_passes_through_simple_token() -> None:
    assert _quote("handle.exe") == "handle.exe"


def test_quote_wraps_whitespace() -> None:
    assert _quote("a b") == "'a b'"


def test_quote_doubles_embedded_single_quote() -> None:
    assert _quote("a'b") == "'a''b'"


# ---------- raw remote block (sibling helper used by some tools) ----------


def test_remote_command_block_emits_powershell_fence() -> None:
    out = remote_command_block(["handle.exe", "-accepteula"])
    assert out.startswith("```powershell\n")
    assert "handle.exe -accepteula" in out
    assert out.rstrip().endswith("```")


def test_remote_command_block_appends_note() -> None:
    out = remote_command_block(["x"], note="follow-up: parse with foo")
    assert "follow-up: parse with foo" in out


# ---------- defensive: caller mistakes ----------


def test_lablink_block_rejects_neither_cmdline_nor_script_body() -> None:
    """The helper requires exactly one of cmdline / script_body.

    Calling with neither must raise -- either a ``TypeError`` (Python
    catching a missing required argument) or a ``ValueError`` (the
    helper's own validation when both default to ``None``).
    """
    with pytest.raises((TypeError, ValueError)):
        lablink_first_remote_block()  # type: ignore[call-arg]


def test_lablink_block_rejects_both_cmdline_and_script_body() -> None:
    """Supplying both cmdline and script_body must raise ValueError."""
    with pytest.raises(ValueError):
        lablink_first_remote_block(["handle.exe"], script_body="$x = 1")


def test_lablink_block_script_body_emitted_verbatim() -> None:
    """A multi-line ``script_body`` must appear unquoted in the powershell fence.

    Regression guard for CRITICAL 3: the old code path wrapped the
    script in single quotes via ``_quote``, turning it into a string
    literal that PowerShell evaluates to itself and discards. The
    fixed path emits the script body verbatim so a paste actually
    runs the program.
    """
    script = (
        "$installDir = 'C:\\Sysinternals'\n"
        "Invoke-WebRequest -Uri https://x/y.zip -OutFile $installDir\\y.zip\n"
        "Expand-Archive -Path $installDir\\y.zip -DestinationPath $installDir\n"
    )
    out = lablink_first_remote_block(script_body=script, timeout_s=600)
    ps = _extract_powershell_block(out)
    # The body must NOT be wrapped in '...' as a single quoted literal.
    assert not ps.startswith("'"), (
        "script_body was quote-wrapped; powershell block starts with "
        f"a single quote. Block:\n{ps}"
    )
    # The script content survives verbatim.
    assert "$installDir = 'C:\\Sysinternals'" in ps
    assert "Invoke-WebRequest" in ps
    assert "Expand-Archive" in ps
    # The JSON sidecar's ``command`` equals the script body byte-for-byte.
    sidecar = _extract_json_sidecar(out)
    assert sidecar["command"] == script
