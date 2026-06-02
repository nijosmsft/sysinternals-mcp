"""Parser for ``strings.exe`` output.

strings.exe emits one extracted string per line. With ``-o`` it
prepends a byte offset; with ``-n <N>`` it filters by minimum length.

Sample::

    Strings v2.54 - Search for ANSI and UNICODE strings in binary images.
    Copyright (C) 1999-2024 Mark Russinovich

    !This program cannot be run in DOS mode.
    RichPE
    .text
    `.rdata

We return a DataFrame with columns Offset (if -o), String.
"""

from __future__ import annotations

import re

import pandas as pd

_OFFSET_RE = re.compile(r"^\s*(?P<offset>[0-9A-Fa-f]+):\s*(?P<value>.*)$")
_BANNER_PREFIXES = (
    "strings v",
    "copyright",
    "sysinternals",
)


def parse_strings_output(text: str) -> pd.DataFrame:
    """Parse strings.exe stdout. Drops banner. Detects -o offset prefix."""
    if not text:
        return pd.DataFrame(columns=["Offset", "String"])
    rows: list[dict[str, str]] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        low = stripped.lower()
        if any(low.startswith(p) for p in _BANNER_PREFIXES):
            continue
        m = _OFFSET_RE.match(line)
        if m:
            rows.append(
                {
                    "Offset": m.group("offset"),
                    "String": m.group("value"),
                }
            )
        else:
            rows.append({"Offset": "", "String": stripped})
    return pd.DataFrame(rows, columns=["Offset", "String"])


__all__ = ["parse_strings_output"]
