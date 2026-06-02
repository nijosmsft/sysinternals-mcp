"""Verify the server has zero coupling to any remote-execution MCP.

The contract: NO source file under ``src/sysinternals_mcp/`` imports
``lablink`` (or any equivalent remote-exec MCP module). LabLink may
be named in docs as one example transport, alongside PSRemoting and
manual scp -- but the source must remain transport-agnostic.

We grep the source tree for forbidden import / from-import lines.
The docs grep is intentionally a different test: docs MAY mention
LabLink.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "sysinternals_mcp"

# Forbidden module names — any module whose presence would mean we're
# importing a remote-exec transport directly.
FORBIDDEN_MODULES = (
    "lablink",
    "lablink_mcp",
    "lablink_agent",
)

# Patterns that MUST NOT appear in source. Match both:
#   import lablink
#   from lablink import foo
#   from lablink.x import foo
_IMPORT_PATTERNS = [
    re.compile(rf"^\s*import\s+{re.escape(mod)}(\.|\s|$)", re.MULTILINE)
    for mod in FORBIDDEN_MODULES
] + [
    re.compile(rf"^\s*from\s+{re.escape(mod)}(\.|\s)", re.MULTILINE)
    for mod in FORBIDDEN_MODULES
]


def test_no_imports_of_remote_exec_mcps() -> None:
    offenders: list[tuple[Path, str]] = []
    for py in SRC_ROOT.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for pattern in _IMPORT_PATTERNS:
            for match in pattern.finditer(text):
                offenders.append((py, match.group(0).strip()))
    assert offenders == [], (
        "The server must not import any remote-execution MCP "
        f"directly. Offending lines: {offenders}"
    )


def test_no_lablink_mention_in_source_modules() -> None:
    """Even string literals shouldn't name LabLink as a default transport.

    The only acceptable mention is when a tool emits a *runbook* that
    describes transport options (PSRemoting / LabLink / scp). Those
    runbooks are explicitly allowed because they're docs-as-tools, not
    imports. We verify this by allowing the substring `LabLink` only
    inside the allow-listed modules; every other source file must be
    free of it.
    """
    allowed = {
        SRC_ROOT / "tools" / "procmon.py",
        SRC_ROOT / "tools" / "setup.py",
        SRC_ROOT / "tools" / "_common.py",  # v0.2 LabLink-first helper
        SRC_ROOT / "tools" / "bootstrap.py",  # v0.2 bootstrap runbook
        SRC_ROOT / "tools" / "eula_tool.py",  # v0.2 EULA-consent prompt
        SRC_ROOT / "app.py",
    }
    offenders: list[Path] = []
    for py in SRC_ROOT.rglob("*.py"):
        if py in allowed:
            continue
        text = py.read_text(encoding="utf-8")
        if "lablink" in text.lower():
            offenders.append(py)
    assert offenders == [], (
        "Only docs-as-tools modules (tools/procmon.py runbook, "
        "tools/setup.py remote block, tools/_common.py LabLink-first "
        "helper, tools/bootstrap.py, tools/eula_tool.py, app.py "
        f"instructions) may mention LabLink. Offenders: {[str(p) for p in offenders]}"
    )


def test_json_sidecar_blocks_have_no_python_imports() -> None:
    """The LabLink-first JSON sidecar emits a remote dispatch payload.

    The sidecar must contain only execute-command primitives -- no
    Python ``import`` strings that could be mistaken for executable
    code by an LLM, no ``from X import`` lines, no Python module
    references. This locks the helper into a transport-agnostic
    JSON-only shape.
    """
    common = SRC_ROOT / "tools" / "_common.py"
    text = common.read_text(encoding="utf-8")
    # The helper body is what builds the sidecar; ensure it never
    # writes "import" or "from X import" into the JSON it emits.
    # We scan only the lines that look like they construct the JSON
    # body (the literal "json_lines" list and surrounding format calls).
    import re

    in_helper = False
    forbidden_in_emitted_json = ("import ", "from ")
    for line in text.splitlines():
        if "def lablink_first_remote_block" in line:
            in_helper = True
            continue
        if in_helper and line.startswith("def ") and "lablink_first" not in line:
            in_helper = False
        if not in_helper:
            continue
        # We allow these tokens in docstring/comment lines; only check
        # actual emitted JSON string literals.
        match = re.search(r'"([^"]*)"', line)
        if not match:
            continue
        emitted = match.group(1)
        for bad in forbidden_in_emitted_json:
            assert bad not in emitted, (
                f"JSON sidecar must not emit Python {bad!r}: {line.strip()}"
            )
