"""Evidence-related MCP tools.

Both tools no-op gracefully when the optional ``evidence-store``
library is missing or ``SYSINTERNALS_MCP_EVIDENCE_PATH`` is unset.
This keeps the server usable without any optional federation
infrastructure.
"""

from __future__ import annotations

import pandas as pd

from sysinternals_mcp import evidence_integration as ev
from sysinternals_mcp.app import mcp
from sysinternals_mcp.formatting.markdown import format_table

_VALID_TYPES = ("machine",)


@mcp.tool()
def get_evidence_status() -> str:
    """Report whether the evidence-store federation hook is active.

    The hook requires both gates to be open: the optional library
    must be importable AND ``SYSINTERNALS_MCP_EVIDENCE_PATH`` must be
    set to a writable directory.
    """
    rows = [
        {
            "Gate": "G1: evidence_store library",
            "Status": "available" if ev.is_available() else "missing",
            "Detail": (
                "ok"
                if ev.is_available()
                else f"{ev.availability_error()} -- install the optional "
                "`evidence-store` package to enable."
            ),
        },
        {
            "Gate": "G2: " + ev.EVIDENCE_ENV_VAR,
            "Status": "set" if ev.is_configured() else "unset",
            "Detail": (
                str(ev.evidence_root())
                if ev.is_configured()
                else f"Set `{ev.EVIDENCE_ENV_VAR}` to a writable directory "
                "to enable persistence."
            ),
        },
    ]
    df = pd.DataFrame(rows)
    summary = "**Active**" if ev.both_gates_open() else "**Inactive (no-op)**"
    return (
        f"**Evidence federation status**: {summary}\n\n"
        + format_table(df, max_rows=10)
        + "\n\n"
        + (
            "Entity registrations from sysinternals-mcp are persisted "
            "to per-machine SQLite files under "
            f"`{ev.evidence_root()}`.\n"
            if ev.both_gates_open()
            else "When inactive, all evidence-writing tools return "
            "friendly no-op markdown and persist nothing.\n"
        )
    )


@mcp.tool()
def get_entities(
    entity_type: str = "machine",
    filter: str | None = None,
    max_rows: int = 50,
) -> str:
    """List entities registered by sysinternals-mcp in the evidence store.

    Args:
        entity_type: One of ``"machine"`` (only type supported by
            sysinternals-mcp today -- there are no traces).
        filter: Case-insensitive substring filter on the entity's
            primary name column (``hostname`` for machines).
        max_rows: Truncate the table to this many rows. Default 50.
    """
    if entity_type not in _VALID_TYPES:
        valid = ", ".join(_VALID_TYPES)
        return f"Unknown entity_type `{entity_type}`. Valid: {valid}."

    if not ev.both_gates_open():
        return (
            f"**Evidence federation inactive.** Call "
            f"`get_evidence_status` for gate-by-gate detail. "
            "Entities are not persisted, so no rows can be listed."
        )

    rows = ev.list_entities(entity_type, filter, max_rows)
    if not rows:
        suffix = f" matching `{filter}`" if filter else ""
        return f"*No `{entity_type}` entities registered{suffix}.*"
    df = pd.DataFrame(rows)
    return (
        f"**{entity_type.capitalize()} entities** ({len(df):,})\n\n"
        + format_table(df, max_rows=max_rows)
    )
