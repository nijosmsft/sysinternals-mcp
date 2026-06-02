"""Evidence-store federation hook.

Two independent gates must both pass for any entity registration:

- **G1**: the optional ``evidence-store`` Python package is
  installable. Tested by import.
- **G2**: ``SYSINTERNALS_MCP_EVIDENCE_PATH`` environment variable is
  set to a writable directory.

When either gate fails this module exposes friendly no-op helpers so
the rest of the server still loads. The gates are inspected lazily so
the env var can change without restarting the process (mostly useful
for tests).

For sysinternals there are no traces -- entities are machine-scoped.
``register_local_machine`` records the running host so that later
queries (e.g. ``get_entities(entity_type='machine')``) can join across
sessions.
"""

from __future__ import annotations

import os
import socket
import sqlite3
from pathlib import Path

# Gate 1 -- the optional dependency.
try:  # pragma: no cover -- gate is exercised in tests via stubs.
    import evidence_store  # type: ignore[import-not-found]  # noqa: F401

    _G1_AVAILABLE = True
    _G1_ERROR = ""
except Exception as exc:  # noqa: BLE001 -- the lib might not be installed.
    _G1_AVAILABLE = False
    _G1_ERROR = f"evidence_store import failed: {exc}"

EVIDENCE_ENV_VAR = "SYSINTERNALS_MCP_EVIDENCE_PATH"


def is_available() -> bool:
    """Return True when the optional library is importable (Gate 1)."""
    return _G1_AVAILABLE


def availability_error() -> str:
    """Return the import error message when Gate 1 fails."""
    return _G1_ERROR


def is_configured() -> bool:
    """Return True when the env-var Gate 2 is satisfied."""
    return bool(os.environ.get(EVIDENCE_ENV_VAR, "").strip())


def evidence_root() -> Path | None:
    """Return the evidence root directory if Gate 2 holds, else ``None``."""
    val = os.environ.get(EVIDENCE_ENV_VAR, "").strip()
    if not val:
        return None
    return Path(val).expanduser()


def both_gates_open() -> bool:
    """True only when both G1 and G2 are satisfied."""
    return is_available() and is_configured()


def db_path_for(machine_id: str) -> Path | None:
    """Return the per-machine SQLite DB path, or ``None`` if disabled."""
    root = evidence_root()
    if root is None:
        return None
    return root / f"{machine_id}.sqlite"


def _safe_hostname() -> str:
    try:
        return socket.gethostname() or "unknown-host"
    except OSError:
        return "unknown-host"


def register_local_machine() -> str | None:
    """Register the running host as a ``machine`` entity.

    Returns the machine identifier on success, or ``None`` when either
    gate is closed. Safe to call repeatedly -- subsequent calls update
    the ``last_seen`` timestamp.
    """
    if not both_gates_open():
        return None
    machine_id = _safe_hostname().lower()
    db_path = db_path_for(machine_id)
    if db_path is None:
        return None
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS machine (
                machine_id TEXT PRIMARY KEY,
                hostname TEXT NOT NULL,
                first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO machine (machine_id, hostname)
            VALUES (?, ?)
            ON CONFLICT(machine_id) DO UPDATE SET
                last_seen = CURRENT_TIMESTAMP
            """,
            (machine_id, _safe_hostname()),
        )
    return machine_id


def list_entities(entity_type: str, filter_text: str | None, max_rows: int) -> list[dict]:
    """Return registered entities of the given type. Empty when gates closed."""
    if not both_gates_open():
        return []
    machine_id = _safe_hostname().lower()
    db_path = db_path_for(machine_id)
    if db_path is None or not db_path.exists():
        return []
    if entity_type != "machine":
        return []
    sql = "SELECT machine_id, hostname, first_seen, last_seen FROM machine"
    params: tuple = ()
    if filter_text:
        sql += " WHERE hostname LIKE ?"
        params = (f"%{filter_text}%",)
    sql += f" ORDER BY hostname LIMIT {int(max_rows)}"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


__all__ = [
    "EVIDENCE_ENV_VAR",
    "availability_error",
    "both_gates_open",
    "db_path_for",
    "evidence_root",
    "is_available",
    "is_configured",
    "list_entities",
    "register_local_machine",
]
