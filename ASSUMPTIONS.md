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

## A2 — ProcMon `.pmc` binary format: deferred (RESOLVED in v0.2)

**v0.2 status: RESOLVED via CLI driver.** ``get_procmon_capture_commands``
now parses the ``.pmcx`` text descriptor into ProcMon ``/Filter`` CLI
args and splices them into the command line inline. No GUI step and
no binary ``.pmc`` file are required to apply a recipe. The historic
problem and resolution are kept below for context.

ProcMon's `.pmc` (Process Monitor Configuration) file is an
undocumented binary format. The canonical way to produce one is to
run ProcMon, configure filters in the UI, and `File → Export
Configuration`. There is no Microsoft-supported library that emits
`.pmc` programmatically.

v0.1 shipped **text descriptors** of the three recipes (operation
name, column whitelist, brief docstring) under
`src/sysinternals_mcp/profiles/procmon/<recipe>.pmcx` (the `.pmcx`
extension makes it explicit these are not native `.pmc` files). The
loading workflow at the time required:

1. The operator opens ProcMon manually.
2. **File → Filter** and applies the operation/process filters
   described in the `.pmcx` descriptor.
3. The capture commands use `/AcceptEula /BackingFile <out> /Quiet`
   to start the capture in non-interactive mode.

v0.2 closes the gap by parsing the descriptor's ``[Includes]`` /
``[Excludes]`` sections (``parsing/procmon_filter.py``) into
:class:`FilterRule` objects, then emitting one ``/Filter
"<col>;<op>;<val>;<Include|Exclude>"`` token per rule. Operators may
still use ``/LoadConfig <path>.pmc`` if they prefer the binary form;
both paths produce equivalent filter sets.

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


## A11 — EULA-consent UX gated by three flip paths (v0.2)

The v0.2 bootstrap installer (`bootstrap_sysinternals`) and the
standalone `accept_sysinternals_eula` tool both emit a *CONSENT
REQUIRED* markdown block by default. The LLM is instructed to read
this block to the user verbatim and prompt for a Yes / No-but-install /
Skip-future-prompts response. The block is suppressed only when one
of the following three flip paths is active:

1. The calling tool passed `accept_eula=True`.
2. The MCP server's environment has
   `SYSINTERNALS_MCP_ACCEPT_EULA=1` (any of: 1, true, yes, on).
3. The LLM previously invoked `accept_sysinternals_eula` for the
   target and is now passing `accept_eula=True` back in.

This three-path approach lets a user accept once at first install
(path 1), pre-accept for a whole MCP server session (path 2), or
pre-accept on the host without doing an install (path 3). The
Sysinternals EULA flag is a per-binary HKCU value
`Software\Sysinternals\<Tool>\EulaAccepted=1`; passing
`accept_eula=True` to `bootstrap_sysinternals` writes the flag
for every known binary in one step. Machine-wide acceptance
(`scope='machine'` → HKLM) is documented in the standalone tool
but flagged as requiring an elevated session.
