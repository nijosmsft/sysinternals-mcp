"""Parser for ``accesschk.exe`` text output.

``accesschk -wsq <path>`` produces output like::

      W BUILTIN\\Administrators
      R BUILTIN\\Users
        NT AUTHORITY\\SYSTEM
            FILE_ALL_ACCESS

We extract: ``Principal`` (the account/SID), ``Access`` (R/W/etc. flag
when present), and ``Detail`` (any indented detail line that follows).
The output format varies considerably between modes (``-wsq``, ``-q``,
``-d``, ``-k`` for registry, ``-l`` for SDDL). This parser handles the
``-wsq`` "who has write access" mode commonly used for triage; other
modes still produce a row-per-line table but with sparser column
content.
"""

from __future__ import annotations

import re

import pandas as pd

# Principal row example: "  RW NT AUTHORITY\\SYSTEM" — leading whitespace
# is 1-4 columns (accesschk uses 2 in -wsq, more in some modes). Access
# flag is a short uppercase token (R, W, RW, etc.) or "Deny".
_PRINCIPAL_RE = re.compile(
    r"^\s+(?:(?P<access>[A-Z][A-Za-z]{0,4})\s+)?(?P<principal>\S.*?)\s*$"
)


def parse_accesschk_text(text: str) -> pd.DataFrame:
    """Parse accesschk text output into a DataFrame.

    Columns: ``Object``, ``Principal``, ``Access``, ``Detail``.

    ``Object`` is the indentation-zero header line (typically the
    file/key being audited). Subsequent indented lines are
    principal/access rows. Multi-line detail blocks (typically
    indented more deeply than principals) are joined into the
    ``Detail`` column of the most recent principal.
    """
    rows: list[dict[str, object]] = []
    current_object = ""
    current_principal: dict[str, object] | None = None
    principal_indent: int | None = None

    for raw in text.splitlines():
        if not raw.strip():
            current_principal = None
            principal_indent = None
            continue
        # Skip the accesschk banner.
        if raw.startswith(("Accesschk", "AccessChk", "Copyright", "Sysinternals")):
            continue
        # Indentation indicates row type.
        leading_ws = len(raw) - len(raw.lstrip())
        line = raw.rstrip()

        if leading_ws == 0:
            # Object header.
            current_object = line.strip()
            current_principal = None
            principal_indent = None
            continue

        # Detail-row heuristic: if the line is indented STRICTLY more
        # than the most recent principal row AND we have a current
        # principal to attach to, treat it as a detail continuation
        # (e.g. FILE_ALL_ACCESS lines beneath a principal).
        is_detail = (
            current_principal is not None
            and principal_indent is not None
            and leading_ws > principal_indent
        )
        if is_detail and current_principal is not None:
            detail_text = line.strip()
            existing = str(current_principal.get("Detail") or "")
            current_principal["Detail"] = (
                f"{existing}; {detail_text}" if existing else detail_text
            )
            continue

        m = _PRINCIPAL_RE.match(line)
        if not m:
            continue
        principal = m.group("principal").strip()
        access = (m.group("access") or "").strip()

        row: dict[str, object] = {
            "Object": current_object,
            "Principal": principal,
            "Access": access,
            "Detail": "",
        }
        rows.append(row)
        current_principal = row
        principal_indent = leading_ws

    cols = ["Object", "Principal", "Access", "Detail"]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows, columns=cols)


__all__ = ["parse_accesschk_text"]
