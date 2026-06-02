"""Parser for ``procdump.exe`` stderr / stdout.

ProcDump's output is human-prose, but it always emits a fixed set of
status lines we can extract::

    ProcDump v11.0 - Sysinternals process dump utility
    Copyright (C) 2009-2024 Mark Russinovich and Andrew Richards

    [10:30:15] Dump 1 initiated: C:\\dumps\\notepad.exe_240601_103015.dmp
    [10:30:15] Dump 1 writing: Estimated dump file size is 250 MB.
    [10:30:16] Dump 1 complete: 251 MB written in 0.8 seconds
    [10:30:16] Dump count reached.

We surface the dump-path, dump-size, and timing as a key/value table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ProcDumpResult:
    """Parsed view of procdump output."""

    fields: list[dict[str, str]]
    raw_lines: list[str]
    success: bool


_DUMP_PATH_RE = re.compile(r"Dump \d+ initiated:\s*(?P<path>\S.+)$")
_DUMP_SIZE_RE = re.compile(
    r"Dump \d+ complete:\s*(?P<size>[\d.]+\s*[KMG]?B)\s*written\s+in\s+"
    r"(?P<seconds>[\d.]+)\s*seconds",
    re.IGNORECASE,
)
_FAIL_RE = re.compile(r"\bError\b|\bfailed\b", re.IGNORECASE)


def parse_procdump_output(text: str) -> ProcDumpResult:
    """Parse procdump stderr+stdout into a ProcDumpResult."""
    if not text:
        return ProcDumpResult(fields=[], raw_lines=[], success=False)
    raw_lines: list[str] = []
    fields: list[dict[str, str]] = []
    success = False
    saw_complete = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        raw_lines.append(line)

        m = _DUMP_PATH_RE.search(line)
        if m:
            fields.append({"Field": "Dump path", "Value": m.group("path").strip()})
            continue

        m = _DUMP_SIZE_RE.search(line)
        if m:
            fields.append({"Field": "Dump size", "Value": m.group("size")})
            fields.append({"Field": "Elapsed", "Value": m.group("seconds") + " s"})
            saw_complete = True
            continue

        if "Dump count reached" in line:
            success = True
            continue
        if "Process exited" in line:
            success = True
            continue

    if saw_complete:
        success = True

    if any(_FAIL_RE.search(line) for line in raw_lines):
        success = False

    return ProcDumpResult(fields=fields, raw_lines=raw_lines, success=success)


__all__ = ["ProcDumpResult", "parse_procdump_output"]
