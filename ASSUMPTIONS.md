# Assumptions and judgment calls

Documented up front so future maintainers can validate or revisit
them.

## A1 — Language: pure Python (FastMCP + subprocess + pandas)

Per `sysinternals-mcp-language-analysis.md` the scoring matrix gave
pure Python a 45 vs Python+C# sidecar at 44 and pure Go at 41. The
sidecar is a strict superset of pure Python — adopt it later if PML
parse cost becomes a measured bottleneck. Pure Go would have to
either duplicate the evidence-store DuckDB schema or shell out to a
Python helper to participate in federation; both are worse than
staying in Python.

## A2 — ProcMon `.pmc` binary format: deferred

ProcMon's `.pmc` (Process Monitor Configuration) file is an
undocumented binary format. The canonical way to produce one is to
run ProcMon, configure filters in the UI, and `File → Export
Configuration`. There is no Microsoft-supported library that emits
`.pmc` programmatically.

For v0.1 we ship **text descriptors** of the three recipes (operation
name, column whitelist, brief docstring) under
`src/sysinternals_mcp/profiles/procmon/<recipe>.pmcx` (the `.pmcx`
extension makes it explicit these are not native `.pmc` files). The
loading workflow is:

1. The operator opens ProcMon manually.
2. **File → Filter** and applies the operation/process filters
   described in the `.pmcx` descriptor (or runs ProcMon with
   `/Filter` parameters built from the descriptor).
3. The capture commands use `/AcceptEula /BackingFile <out> /Quiet`
   to start the capture in non-interactive mode.

This is a known limitation. v0.2 candidates:

- Wrap the (community-maintained) `procmon-parser` for read-only
  parsing — it is the only Python library that has ever decoded
  `.pmc`. Last release Dec 2022.
- Generate `.pmc` once via ProcMon UI and bundle the binaries.
  Costs maintenance burden when ProcMon changes its format.
- Drive ProcMon entirely from `/Filter` command-line parameters and
  skip the `.pmc` file altogether. Possible but more verbose for
  multi-filter recipes.

## A3 — `analyze_pml` rounds through ProcMon's `/SaveAs` CSV

Same reason as A2 — no Python library decodes `.pml` reliably for
current ProcMon versions. `procmon.exe /OpenLog X.pml /SaveAs Y.csv`
works on every install. Tradeoff: disk I/O + ~2-4× RAM amplification
during pandas load. Mitigated by `pd.read_csv(chunksize=...)` for
files > 100 MB. Mark in v0.2 plan: revisit if PML volumes warrant a
C# sidecar.

## A4 — Evidence federation: machine-scoped, not trace-scoped

etw-mcp's evidence hook is trace-centric — entities are tied to a
loaded ETL. sysinternals has no equivalent unit of work, so we
register entities scoped to the local machine plus one
`ToolInvocation` observation per live-tool call. This keeps the
same DuckDB schema usable by the federation MCP, just with a
different observation kind.

The implementation in v0.1 is a stub that gracefully degrades to
"no entities registered" when the library is missing OR the env var
is unset (G3 gate from the etw-mcp playbook). Wiring per-invocation
observations into every live tool is a v0.2 task — v0.1 ships the
status surface + the entity-list surface only.

## A5 — `mcp-servers/README.md` does not exist locally

The task asks me to add a row to `C:\git\mcp-servers\README.md` but
that path does not exist on the current machine. The status report
flags this as a deviation — when the mcp-servers repo lands locally
the row should be added with the same shape as the etw-mcp /
perfmon-mcp rows.

## A6 — Default install paths

The Sysinternals Suite has no canonical install path. The three
defaults probed (`C:\Sysinternals\`, `C:\Tools\Sysinternals\`,
`%ProgramFiles%\Sysinternals\`) are the three I have personally
encountered on production lab boxes. Operators with different
conventions set `SYSINTERNALS_MCP_DIR`.

## A7 — HKCU registry probe, not HKLM

Sysinternals binaries write the EULA-accepted flag to HKCU and only
HKCU; there is no machine-wide equivalent. The probe is HKCU-scoped.
This means an MCP server running under a service account different
from the interactive user must pre-accept under the service
account. `check_sysinternals_setup` emits the exact `reg add`
command for the running account.

## A8 — Synthetic test fixtures, no real binaries

Tests use static text fixtures committed under `tests/fixtures/`.
`subprocess.run` is mocked. `find_binary` is mocked. Registry
probes use `monkeypatch`. The test suite must pass on a fresh
checkout with zero Sysinternals binaries installed and zero
`lablink-mcp` or other transport packages installed.

## A9 — Released as MIT, copyright "Nithin Jose"

Matches the etw-mcp / perfmon-mcp family license + copyright. The
Sysinternals binaries themselves remain under the Sysinternals
license and are not redistributed.

## A10 — Repo description shipped to GitHub

> MCP server wrapping the Sysinternals tool suite (Handle, Sigcheck,
> PsList, AccessChk, ProcMon) for Windows process introspection,
> binary triage, and ACL audit. Ships zero binaries — user provides
> Sysinternals install.

Topics: `mcp`, `mcp-server`, `windows`, `sysinternals`, `procmon`,
`ai-tools`.
