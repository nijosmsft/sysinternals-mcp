"""Analyze a ``.pml`` trace by shelling ProcMon and reading the CSV.

ProcMon's ``.pml`` format is binary and undocumented; the only sane
path is to convert to CSV (or XML) via ProcMon itself and read the
result with pandas. We use ``procmon.exe /OpenLog X.pml /SaveAs Y.csv
/Quiet`` and then summarize the events.

The native ``procmon-parser`` PyPI library exists but is unmaintained
and inconsistent across ProcMon versions -- per ASSUMPTIONS.md A3 we
prefer the shell-out path.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class PmlSummary:
    """Result of analyzing a ``.pml`` file."""

    total_rows: int
    top_processes: pd.DataFrame
    op_class_counts: pd.DataFrame
    error_count: int
    columns: list[str]


_EXPECTED_COLUMNS = (
    "Time of Day",
    "Process Name",
    "PID",
    "Operation",
    "Path",
    "Result",
    "Detail",
)


def convert_pml_to_csv(
    procmon_path: Path,
    pml_path: Path,
    csv_path: Path,
    timeout: int = 600,
) -> None:
    """Shell out to ProcMon to convert ``pml`` -> ``csv``.

    Raises ``RuntimeError`` on subprocess failure.
    """
    cmd = [
        str(procmon_path),
        "/OpenLog",
        str(pml_path),
        "/SaveAs",
        str(csv_path),
        "/Quiet",
        "/AcceptEula",
    ]
    completed = subprocess.run(  # noqa: S603 — operator-supplied procmon path
        cmd, capture_output=True, text=True, timeout=timeout, check=False
    )
    if completed.returncode != 0 or not csv_path.exists():
        raise RuntimeError(
            f"procmon.exe /SaveAs failed (exit {completed.returncode}): "
            f"{completed.stderr.strip()}"
        )


def _classify_op(op: str) -> str:
    """Bucket a procmon Operation name into a coarse class."""
    if not isinstance(op, str):
        return "Other"
    o = op
    if o.startswith(("TCP", "UDP")):
        return "Network"
    if o.endswith(("File", "Directory")) or "FileInformation" in o or "FileSystem" in o:
        return "File"
    if o.startswith("Reg"):
        return "Registry"
    if o in {"Process Create", "Process Exit", "Thread Create", "Thread Exit"}:
        return "Process"
    if o.startswith("Load Image"):
        return "Image Load"
    return "Other"


def summarize_csv(csv_path: Path, top_n: int = 20) -> PmlSummary:
    """Load a ProcMon CSV and produce summary tables."""
    chunks: list[pd.DataFrame] = []
    # Chunked read keeps memory bounded for multi-GB traces.
    reader = pd.read_csv(
        csv_path,
        chunksize=200_000,
        low_memory=False,
        on_bad_lines="skip",
    )
    for chunk in reader:
        chunks.append(chunk)
    if not chunks:
        return PmlSummary(
            total_rows=0,
            top_processes=pd.DataFrame(columns=["Process Name", "Events"]),
            op_class_counts=pd.DataFrame(columns=["Class", "Events"]),
            error_count=0,
            columns=[],
        )
    df = pd.concat(chunks, ignore_index=True)

    columns = list(df.columns)
    proc_col = "Process Name" if "Process Name" in columns else columns[1]
    op_col = "Operation" if "Operation" in columns else None
    result_col = "Result" if "Result" in columns else None

    proc_summary = (
        df.groupby(proc_col, dropna=False)
        .size()
        .reset_index(name="Events")
        .sort_values("Events", ascending=False)
        .head(top_n)
        .rename(columns={proc_col: "Process Name"})
        .reset_index(drop=True)
    )

    if op_col is not None:
        df["__class__"] = df[op_col].map(_classify_op)
        op_summary = (
            df.groupby("__class__")
            .size()
            .reset_index(name="Events")
            .rename(columns={"__class__": "Class"})
            .sort_values("Events", ascending=False)
            .reset_index(drop=True)
        )
    else:
        op_summary = pd.DataFrame(columns=["Class", "Events"])

    if result_col is not None:
        error_mask = ~df[result_col].astype(str).str.upper().isin(
            ["SUCCESS", "NAME COLLISION", "REPARSE", "BUFFER OVERFLOW"]
        )
        error_count = int(error_mask.sum())
    else:
        error_count = 0

    return PmlSummary(
        total_rows=len(df),
        top_processes=proc_summary,
        op_class_counts=op_summary,
        error_count=error_count,
        columns=columns,
    )


def analyze_pml_file(
    procmon_path: Path,
    pml_path: Path,
    top_n: int = 20,
    csv_path: Path | None = None,
) -> PmlSummary:
    """End-to-end: convert ``pml`` to CSV, summarize, return ``PmlSummary``.

    If ``csv_path`` is given the intermediate CSV is kept there
    (useful for tests). Otherwise it goes to a temporary file that is
    cleaned up on success.
    """
    if not pml_path.exists():
        raise FileNotFoundError(f"PML file not found: {pml_path}")

    cleanup = False
    if csv_path is None:
        fd, tmp = tempfile.mkstemp(suffix=".csv", prefix="procmon_")
        os.close(fd)
        csv_path = Path(tmp)
        cleanup = True

    try:
        convert_pml_to_csv(procmon_path, pml_path, csv_path)
        return summarize_csv(csv_path, top_n=top_n)
    finally:
        if cleanup and csv_path.exists():
            try:
                csv_path.unlink()
            except OSError:
                pass


__all__ = [
    "PmlSummary",
    "analyze_pml_file",
    "convert_pml_to_csv",
    "summarize_csv",
]
