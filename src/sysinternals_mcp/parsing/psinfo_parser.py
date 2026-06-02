"""Parser for ``psinfo.exe`` text output.

PsInfo dumps system metadata as key-value lines, e.g.::

    PsInfo v1.79 - Local and remote system information viewer
    Copyright (C) 2001-2024 Mark Russinovich

    System information for \\\\DESKTOP-ABC:
    Uptime:                    5 days 12 hours 30 minutes 15 seconds
    Kernel version:            Windows 10 Pro, Multiprocessor Free
    Product type:              Professional
    Product version:           10.0
    Service pack:              0
    Kernel build number:       22621
    Registered organization:   Contoso
    Registered owner:          testuser
    Install date:              1/1/2024, 9:00:00 AM
    Activation status:         Activated
    IE version:                11.0000
    System root:               C:\\Windows
    Processors:                80
    Processor speed:           2.3 GHz
    Processor type:            Intel(R) Xeon(R) Silver 4316 CPU @
    Physical memory:           131072 MB
    Video driver:              NVIDIA Quadro RTX 4000

The parser produces a list of ``(Field, Value)`` rows and
preserves order. With ``-d`` ``-s`` ``-h``, additional sections may
follow (Disk volumes, Hotfixes, Software). We surface those as a
separate ``sections`` map keyed by the section title.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PsInfoSummary:
    """Parsed psinfo output."""

    fields: list[dict[str, str]]
    sections: dict[str, list[str]]


def parse_psinfo_output(text: str) -> PsInfoSummary:
    """Parse psinfo stdout. Empty input returns an empty summary."""
    if not text:
        return PsInfoSummary(fields=[], sections={})
    lines = text.splitlines()
    fields: list[dict[str, str]] = []
    sections: dict[str, list[str]] = {}
    current_section: str | None = None

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            current_section = None
            continue
        # Skip banner / copyright / "System information for"
        low = stripped.lower()
        if low.startswith("psinfo v") or low.startswith("copyright"):
            continue
        if low.startswith("system information for"):
            continue
        if low.startswith("sysinternals"):
            continue

        # A line ending with ":" that doesn't contain a value is a
        # section header (e.g. "Disk volumes:", "Hotfixes:").
        if stripped.endswith(":") and ":" not in stripped[:-1]:
            current_section = stripped.rstrip(":").strip()
            sections.setdefault(current_section, [])
            continue

        if current_section is not None:
            sections[current_section].append(stripped)
            continue

        # Otherwise: "Field: value" key-value row.
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if key:
                fields.append({"Field": key, "Value": val})

    return PsInfoSummary(fields=fields, sections=sections)


__all__ = ["PsInfoSummary", "parse_psinfo_output"]
