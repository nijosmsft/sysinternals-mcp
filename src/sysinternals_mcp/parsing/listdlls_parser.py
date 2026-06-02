"""Parser for ``listdlls.exe`` text output.

Sample::

    ListDLLs v3.3 - List loaded modules
    Copyright (C) 1997-2024 Mark Russinovich

    ------------------------------------------------------------------------------
    explorer.exe pid: 3204
    Command line: C:\\Windows\\Explorer.EXE

           Base                Size      Path
        0x00007ff7c2b40000    0x52000    C:\\Windows\\explorer.exe
        0x00007ffd7d3a0000   0x213000    C:\\Windows\\SYSTEM32\\ntdll.dll
        0x00007ffd7c460000    0xc7000    C:\\Windows\\System32\\KERNEL32.DLL

    ------------------------------------------------------------------------------
    notepad.exe pid: 5120
    ...

We parse into a DataFrame with columns Process, PID, Base, Size, Path.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class _State:
    process: str = ""
    pid: str = ""


def parse_listdlls_text(text: str) -> pd.DataFrame:
    """Parse listdlls stdout into a DataFrame."""
    if not text:
        return pd.DataFrame(columns=["Process", "PID", "Base", "Size", "Path"])
    rows: list[dict[str, str]] = []
    state = _State()
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("-"):
            continue
        if stripped.lower().startswith("listdlls") or stripped.startswith("Copyright"):
            continue
        if stripped.startswith("Command line:"):
            continue
        if "pid:" in stripped:
            # "explorer.exe pid: 3204"
            parts = stripped.split("pid:", 1)
            state.process = parts[0].strip()
            state.pid = parts[1].strip().split()[0] if parts[1].strip() else ""
            continue
        if stripped.startswith("Base"):
            continue
        # DLL row: leading whitespace + 0xBASE 0xSIZE  path
        if not stripped.startswith("0x"):
            continue
        tokens = stripped.split(None, 2)
        if len(tokens) < 3:
            continue
        rows.append(
            {
                "Process": state.process,
                "PID": state.pid,
                "Base": tokens[0],
                "Size": tokens[1],
                "Path": tokens[2],
            }
        )
    return pd.DataFrame(
        rows, columns=["Process", "PID", "Base", "Size", "Path"]
    )


def summarize_listdlls(df: pd.DataFrame) -> pd.DataFrame:
    """Per-(Process, PID) DLL count."""
    if df.empty:
        return pd.DataFrame(columns=["Process", "PID", "DLLs"])
    g = (
        df.groupby(["Process", "PID"], as_index=False)
        .size()
        .rename(columns={"size": "DLLs"})
        .sort_values("DLLs", ascending=False, ignore_index=True)
    )
    return g


__all__ = ["parse_listdlls_text", "summarize_listdlls"]
