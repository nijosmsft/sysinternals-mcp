"""Parser for ``coreinfo.exe`` text output.

Coreinfo dumps CPU topology and cache hierarchy as plain text — no
CSV mode. Sample output::

    Coreinfo v3.6
    Copyright (C) 2008-2024 Mark Russinovich

    Intel(R) Xeon(R) Silver 4316 CPU @ 2.30GHz
    Intel64 Family 6 Model 106 Stepping 6, GenuineIntel
    Microcode signature: 00000000
    HTT             *       Hyperthreading enabled
    HYPERVISOR      -       Hypervisor is present

    Logical Processor to Socket Map:
    ********--------------------------------  Socket 0
    --------********------------------------  Socket 1

    Logical Processor to NUMA Node Map:
    ********--------------------------------  NUMA Node 0
    --------********------------------------  NUMA Node 1

We surface three views: the feature table (FLAG, support, description),
the topology maps (socket / NUMA / cache), and the raw header lines.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CoreinfoSummary:
    """Parsed view of coreinfo stdout."""

    header_lines: list[str]
    features: list[dict[str, str]]
    topology_maps: list[dict[str, str]]


def parse_coreinfo_output(text: str) -> CoreinfoSummary:
    """Parse coreinfo stdout into a CoreinfoSummary.

    Empty input returns an empty summary (no rows).
    """
    if not text:
        return CoreinfoSummary(header_lines=[], features=[], topology_maps=[])
    lines = text.splitlines()
    header_lines: list[str] = []
    features: list[dict[str, str]] = []
    topology_maps: list[dict[str, str]] = []

    current_map_name: str | None = None
    seen_first_blank = False

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            seen_first_blank = True
            current_map_name = None
            continue

        # Section headers that begin a topology map: end with ":"
        if line.endswith(":") and "Map" in line:
            current_map_name = line.rstrip(":").strip()
            continue

        # Inside a topology map: lines start with stars/dashes.
        if current_map_name is not None and (
            line.startswith("*") or line.startswith("-")
        ):
            # Pattern: "********--------  Socket 0" or similar
            parts = line.split(None, 1)
            if len(parts) >= 2:
                pattern = parts[0]
                label = parts[1]
            else:
                pattern = line.strip()
                label = ""
            topology_maps.append(
                {
                    "Map": current_map_name,
                    "Pattern": pattern,
                    "Label": label,
                }
            )
            continue

        # Feature lines look like:
        #   "HTT             *       Hyperthreading enabled"
        # or "VMX             -       Hardware virtualization"
        # Three whitespace-separated columns: flag, support indicator,
        # description (possibly multi-word).
        tokens = line.split(None, 2)
        if (
            len(tokens) >= 2
            and tokens[1] in {"*", "-"}
            and not line.startswith(" ")
        ):
            features.append(
                {
                    "Feature": tokens[0],
                    "Supported": "yes" if tokens[1] == "*" else "no",
                    "Description": tokens[2] if len(tokens) > 2 else "",
                }
            )
            continue

        # Otherwise it's a header / banner / metadata line.
        if not seen_first_blank or "Coreinfo" in line or "Copyright" in line:
            header_lines.append(line)
        else:
            # Treat as a metadata line we haven't classified yet.
            header_lines.append(line)

    return CoreinfoSummary(
        header_lines=header_lines,
        features=features,
        topology_maps=topology_maps,
    )


__all__ = ["CoreinfoSummary", "parse_coreinfo_output"]
