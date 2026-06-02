"""Parser for ``sigcheck.exe -c`` CSV output.

``sigcheck -c -a -h <path>`` writes CSV like::

    "Path","Verified","Date","Publisher","Company","Description","Product","Product Version","File Version","Machine Type","MD5","SHA1","SHA256","IMP","Strong Name"
    "C:\\Windows\\System32\\notepad.exe","Signed","11:45 AM 6/1/2024","Microsoft Windows","Microsoft Corporation","Notepad","Microsoft Windows Operating System","10.0.22621.1","10.0.22621.1","64-bit","ABC...","DEF...","123...","456...","Valid"

The byte-order mark + comma layout matches the sigcheck `-c` flag.
``sigcheck -ct`` (tab-separated) is also supported as a fallback.
"""

from __future__ import annotations

import csv
import io

import pandas as pd


def parse_sigcheck_csv(text: str) -> pd.DataFrame:
    """Parse sigcheck CSV / TSV output into a DataFrame.

    Returns an empty DataFrame (no columns enforced) when the input is
    empty or only contains a header.
    """
    if not text:
        return pd.DataFrame()

    # Drop UTF-8 / UTF-16 BOMs.
    cleaned = text.lstrip("\ufeff").lstrip("\ufffe")

    # Detect delimiter from the header line.
    first_line = cleaned.splitlines()[0] if cleaned.splitlines() else ""
    delimiter = "\t" if "\t" in first_line and "," not in first_line else ","

    reader = csv.DictReader(io.StringIO(cleaned), delimiter=delimiter)
    rows = [dict(r) for r in reader]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # Normalize key columns: strip whitespace from cell contents.
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()
    return df


__all__ = ["parse_sigcheck_csv"]
