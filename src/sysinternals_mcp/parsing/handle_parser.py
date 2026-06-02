"""Parser for ``handle.exe`` stdout.

``handle.exe -p <process>`` produces output like::

    Nthandle v5.0 - Handle viewer
    Copyright (C) 1997-2022 Mark Russinovich
    Sysinternals - www.sysinternals.com

    chrome.exe pid: 1234 NT AUTHORITY\\SYSTEM
       30: File          (RW-)   C:\\Windows\\System32\\config.dat
       54: Key                   HKLM\\SOFTWARE\\Microsoft
      218: Section               BaseNamedObjects\\__ComCatalogCache__

This parser turns that into a DataFrame with columns ``Process``,
``PID``, ``User``, ``Handle``, ``Type``, ``Access``, ``Name``.

It is permissive: when the input is empty or only contains the banner
the parser returns an empty DataFrame and the caller surfaces a
"no handles" message.
"""

from __future__ import annotations

import re

import pandas as pd

# Process header: "chrome.exe pid: 1234 NT AUTHORITY\\SYSTEM"
_HEADER_RE = re.compile(
    r"^(?P<process>\S.*?)\s+pid:\s+(?P<pid>\d+)\s+(?P<user>.*?)\s*$"
)

# Handle line: "  30: File          (RW-)   C:\\Windows\\System32\\config.dat"
# Access is optional (sections and other types don't always have one).
_HANDLE_RE = re.compile(
    r"^\s*(?P<handle>[0-9A-Fa-f]+):\s+"
    r"(?P<type>\S+)\s*"
    r"(?:\((?P<access>[^)]*)\))?"
    r"\s*(?P<name>.*?)\s*$"
)

_BANNER_PREFIXES = (
    "Nthandle",
    "Copyright",
    "Sysinternals",
)


def parse_handle_text(text: str) -> pd.DataFrame:
    """Parse the stdout of ``handle.exe`` into a DataFrame.

    Returns an empty DataFrame (with the canonical columns) when the
    input contains no handle rows.
    """
    rows: list[dict[str, object]] = []
    current_process = ""
    current_pid = 0
    current_user = ""

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.startswith(_BANNER_PREFIXES):
            continue

        header = _HEADER_RE.match(line)
        if header and "pid:" in line:
            current_process = header.group("process").strip()
            try:
                current_pid = int(header.group("pid"))
            except ValueError:
                current_pid = 0
            current_user = header.group("user").strip()
            continue

        m = _HANDLE_RE.match(line)
        if not m or not current_process:
            continue
        if m.group("type") in {"pid:"}:
            continue
        rows.append(
            {
                "Process": current_process,
                "PID": current_pid,
                "User": current_user,
                "Handle": m.group("handle"),
                "Type": m.group("type"),
                "Access": (m.group("access") or "").strip(),
                "Name": m.group("name").strip(),
            }
        )

    columns = ["Process", "PID", "User", "Handle", "Type", "Access", "Name"]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns)


def summarize_handles(df: pd.DataFrame) -> pd.DataFrame:
    """Return a per-(Process, Type) count summary."""
    if df.empty:
        return pd.DataFrame(columns=["Process", "PID", "Type", "Count"])
    grouped = (
        df.groupby(["Process", "PID", "Type"], dropna=False)
        .size()
        .reset_index(name="Count")
        .sort_values(["Process", "Count"], ascending=[True, False])
        .reset_index(drop=True)
    )
    return grouped


__all__ = ["parse_handle_text", "summarize_handles"]
