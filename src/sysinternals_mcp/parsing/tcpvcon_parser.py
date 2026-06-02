"""Parser for ``tcpvcon.exe -c`` CSV output.

``tcpvcon.exe -a -c -n`` produces a header-less CSV of every active TCP
and UDP endpoint::

    TCP,chrome.exe,7892,ESTABLISHED,10.0.0.5,55012,93.184.216.34,443
    TCP,System,4,LISTENING,0.0.0.0,445,0.0.0.0,0
    UDP,svchost.exe,852,*,0.0.0.0,5353,*,*

Columns: ``Protocol, Process, PID, State, LocalAddr, LocalPort,
RemoteAddr, RemotePort``. ``-n`` keeps numeric ports (no DNS lookup),
``-a`` lists all sockets including UDP. We accept rows with extra
trailing columns (some tcpvcon builds add owning-PID).
"""

from __future__ import annotations

import csv
import io

import pandas as pd

_COLUMNS = (
    "Protocol",
    "Process",
    "PID",
    "State",
    "LocalAddr",
    "LocalPort",
    "RemoteAddr",
    "RemotePort",
)


def parse_tcpvcon_csv(text: str) -> pd.DataFrame:
    """Parse tcpvcon CSV output into a DataFrame.

    Returns an empty DataFrame when ``text`` is blank or contains no
    parseable rows. Banner / copyright lines that tcpvcon writes
    before the CSV are tolerated and skipped.
    """
    if not text:
        return pd.DataFrame(columns=list(_COLUMNS))
    cleaned = text.lstrip("\ufeff").lstrip("\ufffe")
    rows: list[dict[str, str]] = []
    reader = csv.reader(io.StringIO(cleaned))
    for raw in reader:
        if not raw:
            continue
        proto = raw[0].strip().upper()
        if proto not in {"TCP", "UDP", "TCPV6", "UDPV6"}:
            continue
        # Pad short rows so the column mapping is stable.
        padded = list(raw) + [""] * (len(_COLUMNS) - len(raw))
        rows.append({col: padded[i].strip() for i, col in enumerate(_COLUMNS)})
    if not rows:
        return pd.DataFrame(columns=list(_COLUMNS))
    df = pd.DataFrame(rows, columns=list(_COLUMNS))
    return df


__all__ = ["parse_tcpvcon_csv"]
