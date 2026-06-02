# CLAUDE.md

Guidance for AI assistants working on the **sysinternals-mcp** source.
For end-user docs (install, MCP config, tool list) see `README.md`.

## What this repo is

An MCP server that wraps the Microsoft Sysinternals tool suite
(`handle.exe`, `sigcheck.exe`, `pslist.exe`, `accesschk.exe`,
`procmon.exe`) so AI assistants can drive Windows process
introspection, binary triage, ACL audit, and event-trace capture
through MCP tools. Python 3.11+, packaged with `uv`, served over
stdio via FastMCP. Windows-only — every tool ultimately runs a
Sysinternals binary as a subprocess (or emits the command line for a
remote target).

The server **ships zero Sysinternals binaries**. Users download the
suite from <https://learn.microsoft.com/en-us/sysinternals/> and point
the server at the install dir via `SYSINTERNALS_MCP_DIR`.

## Layout

```
src/sysinternals_mcp/
  server.py              entry point — imports each tools.* module and
                         calls mcp.run("stdio")
  app.py                 the single FastMCP("sysinternals-mcp") instance
                         + server instructions
  binary_locator.py      env var > PATH > default paths discovery, cached
  eula.py                HKCU EULA probe + emit "reg add" command
  evidence_integration.py optional evidence-store federation hook
                         (try/except ImportError + env-var gate)
  tools/                 one module per tool group; each module calls
                         @mcp.tool() at import time
    setup.py             check_sysinternals_setup
    handle.py            handle_list, parse_handle_output
    sigcheck.py          sigcheck, parse_sigcheck_output
    pslist.py            pslist, parse_pslist_output
    accesschk.py         accesschk, parse_accesschk_output
    procmon.py           list_procmon_recipes, get_procmon_recipe,
                         get_procmon_capture_commands,
                         get_capture_instructions, analyze_pml
    evidence.py          get_evidence_status, get_entities
  profiles/
    metadata.py          RecipeMeta dataclass + RECIPES dict + loader
    procmon/             bundled ProcMon filter recipes (text/XML
                         descriptors; .pmc binary load deferred — see
                         ASSUMPTIONS.md)
  parsing/
    handle_parser.py     handle.exe stdout text parser
    sigcheck_parser.py   sigcheck CSV parser
    pslist_parser.py     pslist text parser
    accesschk_parser.py  accesschk text parser
    pml_parser.py        shells out to procmon.exe /OpenLog /SaveAs CSV
                         then loads with pandas
  formatting/
    markdown.py          format_table, format_pct, ... (lifted verbatim
                         from etw-mcp)
tests/                   pytest; synthetic fixtures only — no
                         Sysinternals binaries required
pyproject.toml           hatchling build; deps: mcp, pandas, pyarrow;
                         dev: pytest
```

## How tools get registered

Tools are not enumerated by FastMCP automatically — `server.py`
imports every `tools.*` submodule, and each submodule attaches
functions to the shared `mcp` instance via `@mcp.tool()`. **If you
add a new tool module, you must add an `import` line to `server.py`
or the tool will not be visible.**

## Three lifecycle shapes

1. **One-shot live tool** (handle, sigcheck, pslist, accesschk) —
   single command, stdout parsed and returned as markdown.
2. **ProcMon capture** (procmon) — paired start/stop pattern with a
   filter recipe; ProcMon writes a `.pml` file; analysis tool decodes
   it.
3. **PML analysis** (analyze_pml) — file-in, markdown-out.

All three share the same `target=local|remote` contract.

## Remote-friendly design contract

Every live-execute tool:

- Takes `target: str = "local"`.
- `target="local"` → server runs the binary as a subprocess, parses
  stdout, returns markdown.
- `target="remote"` → server returns the exact command line as a
  fenced ```powershell``` block. **The server never executes against a
  remote machine.**
- Has a sibling `parse_<tool>_output(text)` so the operator can pipe
  remote stdout back into the same markdown shape.
- Takes every file path as an explicit arg — never defaults to a
  local-only path.

There are **zero imports of `lablink-mcp` or any other
remote-execution MCP** in the source. LabLink is named in docs as one
example transport, alongside PowerShell remoting and manual scp.

## Binary discovery

`binary_locator.find_binary("handle.exe")` resolves a path in this
order:

1. `SYSINTERNALS_MCP_DIR` env var, joined with the requested name.
2. `where.exe <name>` (PATH lookup).
3. Default install paths in order: `C:\Sysinternals\`,
   `C:\Tools\Sysinternals\`, `%ProgramFiles%\Sysinternals\`.

The result is cached for the process lifetime. To re-probe after
moving the install, restart the server.

Every live tool that needs a binary calls `find_binary()` first. When
the binary is missing the tool returns a friendly markdown error
naming the env var override and the download URL — it never raises.

## EULA handling

Every Sysinternals binary prompts on first run and writes
`HKCU\Software\Sysinternals\<Tool>\EulaAccepted=1` afterward. The
server:

- Always passes `-accepteula` (or the tool's equivalent flag) on every
  invocation, so a fresh user account works first try.
- Probes the HKCU registry value in `check_sysinternals_setup` so the
  operator can pre-accept under the runtime account (useful when the
  MCP server runs under a service account different from the
  interactive user).
- For unaccepted tools, surfaces the exact `reg add` command in the
  `Action` column of the setup table.

The probe targets `HKCU` (the current user), **never** `HKLM`.

## Conventions

- **Tool docstrings are user-visible.** FastMCP exposes them as the
  tool description in the MCP protocol. Keep them concrete.
- **Every tool returns a markdown string.** Use `format_table(df)` /
  `format_pct(value)`. Do not return DataFrames or raw dicts.
- **No emojis, no decorative output.** Markdown tables and plain
  headers only.
- **Synthetic fixtures only in tests.** No Sysinternals binary
  required. Mock `subprocess.run`, mock `find_binary`, mock registry
  probes via `monkeypatch`.

## Commits

- **All commits must be signed off** (`git commit -s`).
- Subject line is a single short imperative sentence ("Add ProcMon
  recipe metadata loader", "Wire HKCU EULA probe").
- Small, single-concern commits.
- **Don't commit unless the user asks.**

## Things to know before changing behavior

- **Renaming or removing an `@mcp.tool()` is a breaking change** for
  any agent already configured against this server. Bump `version` in
  `pyproject.toml` and note it.
- **FastMCP's `instructions` string** (in `app.py`) is what clients
  see as server-level guidance. Keep it in sync with the actual tool
  set when adding or removing tools.
- **`analyze_pml` rounds through ProcMon's `/SaveAs` CSV** — large
  `.pml` files (a busy machine for 30s = 1+ GB) inflate 2-4× in RAM
  when read with pandas. Stream in chunks for anything over 100 MB.
