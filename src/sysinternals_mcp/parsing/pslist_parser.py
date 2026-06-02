"""Parser for ``pslist.exe`` stdout.

Default ``pslist`` output looks like::

    PsList v1.41 - ...
    Copyright (C) ...
    Sysinternals - ...

    Process information for HOSTNAME:

    Name                Pid Pri Thd  Hnd      Priv        CPU Time    Elapsed Time
    Idle                  0   0   8    0         0    00:01:23.456    01:00:00.000
    System                4   8 230 6543       192    00:00:34.567    01:00:00.000
    ...
"""

from __future__ import annotations

import re

import pandas as pd

_HEADER_RE = re.compile(
    r"^\s*Name\s+Pid\s+Pri\s+Thd\s+Hnd\s+Priv\s+CPU Time\s+Elapsed Time\s*$"
)

# Row format: name (may contain spaces? Sysinternals truncates to no spaces),
# pid pri thd hnd priv cputime elapsedtime.
_ROW_RE = re.compile(
    r"^\s*(?P<name>\S+)\s+"
    r"(?P<pid>\d+)\s+"
    r"(?P<pri>-?\d+)\s+"
    r"(?P<thd>\d+)\s+"
    r"(?P<hnd>\d+)\s+"
    r"(?P<priv>\d+)\s+"
    r"(?P<cpu>[\d:.]+)\s+"
    r"(?P<elapsed>[\d:.]+)\s*$"
)


def parse_pslist_text(text: str) -> pd.DataFrame:
    """Parse pslist stdout into a DataFrame.

    Returns the columns ``Name, PID, Pri, Thd, Hnd, Priv, CPU Time,
    Elapsed Time``. Header rows and the banner are tolerated.
    """
    rows: list[dict[str, object]] = []
    in_table = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        if _HEADER_RE.match(line):
            in_table = True
            continue
        if not in_table:
            continue
        m = _ROW_RE.match(line)
        if not m:
            continue
        rows.append(
            {
                "Name": m.group("name"),
                "PID": int(m.group("pid")),
                "Pri": int(m.group("pri")),
                "Thd": int(m.group("thd")),
                "Hnd": int(m.group("hnd")),
                "Priv": int(m.group("priv")),
                "CPU Time": m.group("cpu"),
                "Elapsed Time": m.group("elapsed"),
            }
        )
    cols = ["Name", "PID", "Pri", "Thd", "Hnd", "Priv", "CPU Time", "Elapsed Time"]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows, columns=cols)


def apply_filter(df: pd.DataFrame, name_filter: str) -> pd.DataFrame:
    """Filter rows whose Name contains ``name_filter`` (case-insensitive)."""
    if not name_filter:
        return df
    if df.empty:
        return df
    mask = df["Name"].astype(str).str.contains(name_filter, case=False, regex=False)
    return df[mask].reset_index(drop=True)


__all__ = ["apply_filter", "parse_pslist_text"]
