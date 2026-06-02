"""Parser for ``autorunsc.exe -ct`` (tab-separated) output.

``autorunsc.exe -accepteula -nobanner -a * -c -s -h *`` produces TSV
listing every autostart entry. The default column set:

    Time, Entry Location, Entry, Enabled, Category, Profile, Description,
    Signer, Company, Image Path, Version, Launch String, MD5, SHA-1,
    PESHA-1, PESHA-256, SHA-256, IMP

We expose this as a DataFrame. The parser tolerates BOMs, the
short-form CSV variant (``-c`` without ``-ct``), and rows where some
later columns are missing (older autorunsc builds).
"""

from __future__ import annotations

import csv
import io

import pandas as pd


def parse_autorunsc_output(text: str) -> pd.DataFrame:
    """Parse autorunsc CSV or TSV stdout into a DataFrame.

    Empty / banner-only input returns an empty DataFrame (no columns
    enforced — callers branch on ``df.empty``).
    """
    if not text:
        return pd.DataFrame()
    cleaned = text.lstrip("\ufeff").lstrip("\ufffe")
    lines = cleaned.splitlines()
    if not lines:
        return pd.DataFrame()
    # Find the header line — autorunsc may prepend banner text.
    header_idx = None
    for i, line in enumerate(lines):
        low = line.lower()
        if low.startswith("time\t") or low.startswith('"time"') or low.startswith("time,"):
            header_idx = i
            break
    if header_idx is None:
        return pd.DataFrame()
    body = "\n".join(lines[header_idx:])
    first = lines[header_idx]
    delimiter = "\t" if "\t" in first else ","
    reader = csv.DictReader(io.StringIO(body), delimiter=delimiter)
    rows = [dict(r) for r in reader]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
    return df


__all__ = ["parse_autorunsc_output"]
