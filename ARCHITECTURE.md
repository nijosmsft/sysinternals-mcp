# Architecture

sysinternals-mcp is a thin, transport-agnostic wrapper around the
Microsoft Sysinternals binaries. It exposes MCP tools that either
execute a binary on the local machine and return parsed markdown, or
emit a paste-ready command for the operator to run on a remote
target.

There are three lifecycle shapes covered by the tool set, plus two
cross-cutting concerns (binary discovery + EULA handling) and an
optional federation hook.

## 1. One-shot live tool lifecycle

```
caller -> tool(target="local", ...)
              | find_binary("<tool>.exe")
              | subprocess.run([binary, "-accepteula", ...], capture)
              | parse_<tool>_output(stdout)
              | format_table(df) -> markdown
              v
            markdown returned to caller
```

For `target="remote"` the server short-circuits at the `find_binary`
step and instead returns a fenced ```powershell``` block containing
the command that the operator should run on the target. The operator
then pipes the captured stdout back into the matching
`parse_<tool>_output` tool to get the same markdown shape.

Tools that follow this shape: `handle_list`, `sigcheck`, `pslist`,
`accesschk`, `check_sysinternals_setup`.

## 2. ProcMon capture lifecycle

ProcMon is unique among the Sysinternals tools because it writes a
binary trace file (`.pml`) rather than streaming text to stdout. The
capture model is paired start/stop:

```
get_capture_instructions(recipe, target=..., output_path=...)
   -> markdown runbook with three fenced blocks:
        Step 1 - procmon.exe /AcceptEula /BackingFile <out> /LoadConfig <recipe>
        Step 2 - Start-Sleep -Seconds <duration_s>
        Step 3 - procmon.exe /Terminate
```

For `target="remote"` the runbook adds a "transfer the .pml back"
section with three example transports (PowerShell remoting, an MCP
file-transfer tool such as LabLink, manual scp).

`get_procmon_capture_commands` returns just the three commands when
the operator does not need the prose runbook.

## 3. PML analysis lifecycle

```
analyze_pml(path, top_n=...)
   | find_binary("procmon.exe")
   | subprocess.run([procmon, "/OpenLog", path, "/SaveAs", tmp.csv])
   | pd.read_csv(tmp.csv) (chunked for large files)
   | aggregate: top processes, op-class histogram, error count
   | format_table -> markdown
```

This rounds through ProcMon itself for `.pml` decode because
ProcMon's binary format is undocumented and the one Python parser on
PyPI (`procmon-parser`) is dormant. The round-trip costs disk I/O but
buys correctness on every PML the tooling produces.

## 4. Binary discovery (cross-cutting)

`binary_locator.find_binary(name)` resolves a Sysinternals binary
path in priority order:

1. `SYSINTERNALS_MCP_DIR` env var.
2. `where.exe <name>` (PATH lookup).
3. Default install paths: `C:\Sysinternals\`,
   `C:\Tools\Sysinternals\`, `%ProgramFiles%\Sysinternals\`.

Cached for the process lifetime. Every live tool calls it; missing
binaries return a friendly error pointing at the env var and the
download URL.

## 5. EULA handling (cross-cutting)

Sysinternals binaries write
`HKCU\Software\Sysinternals\<Tool>\EulaAccepted=1` after the first
run with `-accepteula`. The server:

- Always passes the `-accepteula` flag on every subprocess call.
- Probes the HKCU value in `check_sysinternals_setup` so the
  operator can pre-accept under the runtime account.
- For each tool with `EULA accepted? = no`, surfaces the exact
  `reg add` command in the setup-table `Action` column.

The probe is HKCU-scoped because that is where Sysinternals writes
the flag — there is no machine-wide equivalent.

## 6. Evidence federation hook (optional)

Mirrors the etw-mcp pattern: a two-gate import-and-env-var contract.

- **G1: Library present.** The `evidence_store` import is wrapped in
  `try/except ImportError`. If the library is not installed, the
  hook is a no-op.
- **G2: Env var set.** `SYSINTERNALS_MCP_EVIDENCE_PATH` must point at
  a directory. When unset the hook is also a no-op.

When both gates are satisfied, `get_entities` writes machine + module
+ tool-invocation entities to
`$SYSINTERNALS_MCP_EVIDENCE_PATH/<machine_id>/evidence.duckdb`. The
schema is the same per-machine layout the etw-mcp uses, so the same
DuckDB can be queried by the federation MCP across both tools.

## 7. Failure modes

| Failure                          | Surface                                                             |
| -------------------------------- | ------------------------------------------------------------------- |
| Binary not found                 | Friendly markdown — names the env var override + download URL.       |
| EULA not accepted                | `check_sysinternals_setup` surfaces the `reg add` command per tool.  |
| Subprocess non-zero exit         | Returns stderr in a fenced block; never raises out of the tool.      |
| `target` is not `local`/`remote` | Friendly error listing valid values.                                 |
| `analyze_pml` on a missing file  | Friendly error pointing at the explicit `path` arg.                  |
| Evidence library missing         | Friendly note from `get_evidence_status`; `get_entities` no-ops.     |
