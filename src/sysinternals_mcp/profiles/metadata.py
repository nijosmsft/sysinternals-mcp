"""ProcMon recipe metadata + loader.

Each recipe ships a text descriptor (``.pmcx``) that documents the
filter set and points the operator at how to load it -- either by
hand into the ProcMon GUI, or via ``procmon.exe /LoadConfig`` once the
binary ``.pmc`` form is available (deferred per ASSUMPTIONS.md A2).

The shipped descriptors are NOT in ProcMon's undocumented binary
``.pmc`` format. They are plain text describing the filters in the
ProcMon UI vocabulary -- enough for an operator to reconstruct the
configuration manually in one minute. ProcMon will read them only via
the manual filter UI; ``/LoadConfig`` would require the binary form.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources


@dataclass(frozen=True)
class RecipeMeta:
    """Static description of a ProcMon recipe."""

    recipe: str
    title: str
    when_to_use: str
    filter_description: str
    privilege: str
    est_volume: str
    notes: str
    descriptor_filename: str


RECIPES: dict[str, RecipeMeta] = {
    "file_io_only": RecipeMeta(
        recipe="file_io_only",
        title="File I/O only",
        when_to_use=(
            "Diagnose missing files, ACL denies, slow disk I/O, or "
            "file-path-based config probing by a target process."
        ),
        filter_description=(
            "Include events where Operation contains File* "
            "(CreateFile, ReadFile, WriteFile, CloseFile, "
            "QueryDirectory, etc.). Exclude Registry, Network, "
            "Process, and Profiling events."
        ),
        privilege="Admin (ProcMon installs a kernel driver).",
        est_volume="High on a busy box -- 10-100 MB/min. Cap the trace "
        "with `/BackingFile` plus `/Runtime <seconds>`.",
        notes=(
            "If you only need failures, also enable "
            "`Result != SUCCESS` in the GUI after loading."
        ),
        descriptor_filename="file_io_only.pmcx",
    ),
    "network_only": RecipeMeta(
        recipe="network_only",
        title="Network only",
        when_to_use=(
            "Diagnose connection refused / firewall block / TCP "
            "reset behaviour from a specific user-mode process. Use "
            "ETW / pktmon when you need per-packet wire-level data; "
            "this recipe is for `Process X tried to talk to Y:Z`."
        ),
        filter_description=(
            "Include events where Operation contains TCP* or UDP* "
            "(TCPConnect, TCPSend, TCPReceive, TCPDisconnect, "
            "UDPSend, UDPReceive). Exclude everything else."
        ),
        privilege="Admin.",
        est_volume="Medium -- a connection-heavy server can produce "
        "1-5 MB/min.",
        notes=(
            "ProcMon does not see kernel-only TCP traffic (drivers "
            "talking via NDIS/WSK do not raise the Network class). "
            "Use ETW / pktmon for that."
        ),
        descriptor_filename="network_only.pmcx",
    ),
    "process_lifecycle": RecipeMeta(
        recipe="process_lifecycle",
        title="Process + thread lifecycle",
        when_to_use=(
            "Diagnose unexpected spawns, exit codes, hung children, "
            "or service restart loops. Faster than ETW for "
            "long-running observation."
        ),
        filter_description=(
            "Include Process Create, Process Exit, Thread Create, "
            "Thread Exit. Exclude File / Registry / Network."
        ),
        privilege="Admin.",
        est_volume="Low -- typically <1 MB/min unless the box is "
        "fork-bombing.",
        notes=(
            "Pair with `pslist` to confirm what's currently alive at "
            "the moment of the trace."
        ),
        descriptor_filename="process_lifecycle.pmcx",
    ),
}


def list_recipes() -> list[RecipeMeta]:
    """Return all recipes in stable order."""
    return [RECIPES[k] for k in sorted(RECIPES)]


def get_recipe(name: str) -> RecipeMeta | None:
    """Look up a recipe by short name. Case-insensitive."""
    return RECIPES.get(name.lower())


def load_descriptor_text(meta: RecipeMeta) -> str:
    """Read the text-form descriptor (``.pmcx``) shipped in the wheel."""
    pkg = "sysinternals_mcp.profiles.procmon"
    return resources.files(pkg).joinpath(meta.descriptor_filename).read_text(
        encoding="utf-8"
    )


__all__ = [
    "RECIPES",
    "RecipeMeta",
    "get_recipe",
    "list_recipes",
    "load_descriptor_text",
]
