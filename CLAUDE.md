# CLAUDE.md

Guidance for AI assistants working on the **sysinternals-mcp** source.
For end-user docs (install, MCP config, tool list) see `README.md`.

## What this repo is

An MCP server that wraps the Microsoft Sysinternals tool suite
(`handle.exe`, `sigcheck.exe`, `pslist.exe`, `accesschk.exe`,
`procmon.exe`, `tcpvcon.exe`, `autoruns.exe`/`autorunsc.exe`,
`coreinfo.exe`, `psinfo.exe`, `listdlls.exe`, `procdump.exe`,
`strings.exe`) so AI assistants can drive Windows process
introspection, binary triage, ACL audit, network connection
inventory, autostart audit, hardware introspection, crash-dump
collection, and event-trace capture through MCP tools. Python 3.11+,
packaged with `uv`, served over stdio via FastMCP. Windows-only —
every tool ultimately runs a Sysinternals binary as a subprocess (or
emits the command line for a remote target).

The server **ships zero Sysinternals binaries**. Users either point
the server at an existing install via `SYSINTERNALS_MCP_DIR`, or call
`bootstrap_sysinternals` (v0.2) to install the suite via zip /
winget / live downloads.

## Layout

```
src/sysinternals_mcp/
  server.py              entry point — imports each tools.* module and
                         calls mcp.run("stdio")
  app.py                 the single FastMCP("sysinternals-mcp") instance
                         + server instructions (kept in sync with the
                         registered tool set)
  binary_locator.py      env var > PATH > default paths discovery, cached.
                         Knows the full v0.2 binary set via KNOWN_BINARIES.
  eula.py                HKCU EULA probe + emit "reg add" command. v0.2
                         exposes is_eula_pre_accepted() for the
                         SYSINTERNALS_MCP_ACCEPT_EULA env flip.
  install.py             (v0.2) bootstrap install scripts — zip /
                         winget / live, ARM64-aware. Contains
                         consent_required_markdown(),
                         build_install_script(), probe_script(). No
                         imports of any remote-exec MCP.
  evidence_integration.py optional evidence-store federation hook
                         (try/except ImportError + env-var gate)
  tools/                 one module per tool group; each module calls
                         @mcp.tool() at import time
    setup.py             check_sysinternals_setup
    bootstrap.py         (v0.2) bootstrap_sysinternals — HEADLINE
                         feature. CONSENT REQUIRED UX on first call.
    eula_tool.py         (v0.2) accept_sysinternals_eula — emits HKCU
                         or HKLM reg-add script for every known tool.
    handle.py            handle_list, parse_handle_output
    sigcheck.py          sigcheck, parse_sigcheck_output
    pslist.py            pslist, parse_pslist_output
    accesschk.py         accesschk, parse_accesschk_output
                         (v0.2: reg + svc presets via _ACCESS_MODES)
    tcpvcon.py           (v0.2) tcpvcon, parse_tcpvcon_output
    autoruns.py          (v0.2) autoruns, parse_autoruns_output
    coreinfo.py          (v0.2) coreinfo, parse_coreinfo_output
    psinfo.py            (v0.2) psinfo, parse_psinfo_output
    listdlls.py          (v0.2) listdlls, parse_listdlls_output
    procdump.py          (v0.2) procdump, parse_procdump_output
    strings.py           (v0.2) strings, parse_strings_output
    procmon.py           list_procmon_recipes, get_procmon_recipe,
                         get_procmon_capture_commands,
                         get_capture_instructions, analyze_pml
                         (v0.2: /Filter CLI args spliced inline)
    _common.py           remote-dispatch helpers. v0.2 introduced
                         lablink_first_remote_block() which every live
                         tool uses for target="remote" output —
                         emits markdown + JSON sidecar.
    evidence.py          get_evidence_status, get_entities
  profiles/
    metadata.py          RecipeMeta dataclass + RECIPES dict + loader
    procmon/             bundled ProcMon filter recipes (text/XML
                         descriptors; binary .pmc files still deferred)
  parsing/
    handle_parser.py     handle.exe stdout text parser
    sigcheck_parser.py   sigcheck CSV parser
    pslist_parser.py     pslist text parser
    accesschk_parser.py  accesschk text parser
    tcpvcon_parser.py    (v0.2) tcpvcon CSV parser
    autoruns_parser.py   (v0.2) autorunsc CSV parser
    coreinfo_parser.py   (v0.2) coreinfo key/value parser
    psinfo_parser.py     (v0.2) psinfo key/value parser
    listdlls_parser.py   (v0.2) listdlls text parser
    procdump_parser.py   (v0.2) procdump stderr summary parser
    strings_parser.py    (v0.2) strings output parser
    procmon_filter.py    (v0.2) descriptor rules -> /Filter CLI args
                         (closes A2)
    pml_parser.py        shells out to procmon.exe /OpenLog /SaveAs CSV
                         then loads with pandas
  formatting/
    markdown.py          format_table, format_pct, ... (lifted verbatim
                         from etw-mcp)
tests/                   pytest; synthetic fixtures only — no
                         Sysinternals binaries required. 176 tests as
                         of v0.2.
pyproject.toml           hatchling build; deps: mcp, pandas, pyarrow;
                         dev: pytest. version = 0.2.0.
```

## How tools get registered

Tools are not enumerated by FastMCP automatically — `server.py`
imports every `tools.*` submodule, and each submodule attaches
functions to the shared `mcp` instance via `@mcp.tool()`. **If you
add a new tool module, you must add an `import` line to `server.py`
or the tool will not be visible.**

A `test_server_smoke.py` regression test asserts that every expected
tool name is registered after a fresh `from sysinternals_mcp import
server`. Update its `expected` set whenever you add or remove a tool.

## Three lifecycle shapes

1. **One-shot live tool** (handle, sigcheck, pslist, accesschk,
   tcpvcon, autoruns, coreinfo, psinfo, listdlls, procdump, strings)
   — single command, stdout parsed and returned as markdown.
2. **ProcMon capture** (procmon) — paired start/stop pattern with a
   filter recipe; ProcMon writes a `.pml` file; analysis tool decodes
   it. v0.2 splices descriptor rules into `/Filter` CLI args inline.
3. **PML analysis** (analyze_pml) — file-in, markdown-out.

All three share the same `target=local|remote` contract.

## Remote-friendly design contract

Every live-execute tool:

- Takes `target: str = "local"`.
- `target="local"` → server runs the binary as a subprocess, parses
  stdout, returns markdown.
- `target="remote"` → server returns a *LabLink-first dispatch*
  block via `tools/_common.py::lablink_first_remote_block()` — the
  output contains:
  - a fenced ```powershell``` command,
  - a recommended-dispatch order (LabLink → PSRemoting → manual paste),
  - a `parse_with` hint pointing at the matching parser, and
  - a JSON sidecar (`command` / `shell` / `timeout_s` /
    `expected_runtime_s` / `parse_with`) an LLM can hand straight to
    `lablink.execute_command` or equivalent.
  **The server never executes against a remote machine.**
- Has a sibling `parse_<tool>_output(text)` so the operator can pipe
  remote stdout back into the same markdown shape.
- Takes every file path as an explicit arg — never defaults to a
  local-only path.

There are **zero imports of `lablink-mcp` or any other
remote-execution MCP** in the source — enforced by
`tests/test_remote_zero_coupling.py`. LabLink is named in tool output
as the *recommended* transport alongside PSRemoting and manual
paste; that's the limit of the coupling.

## Bootstrap + EULA UX (v0.2 headline)

`bootstrap_sysinternals` is the v0.2 headline feature. It exists so
an LLM can walk a user from "no Sysinternals" to "installed and
EULA-accepted" without leaving the chat.

- **First call** returns a **CONSENT REQUIRED** markdown block with
  the EULA URL, the chosen install method, the install dir, and a
  Yes/No prompt. The LLM is expected to render this to the user
  verbatim.
- **Second call** is made by the LLM with `accept_eula=True` once
  the user answers Yes — it returns the actual install script.
- **Bypass for the whole session**: set
  `SYSINTERNALS_MCP_ACCEPT_EULA=1` on the server before launch;
  `is_eula_pre_accepted()` returns True and the consent block is
  suppressed (with a small "treating as accepted" note).
- `accept_sysinternals_eula(scope="user"|"machine")` exists as a
  separate tool for users who want to pre-accept without installing.

Three install methods supported (`install.py`):

- **zip** — `Invoke-WebRequest` + `Expand-Archive`, ARM64-aware via
  `$env:PROCESSOR_ARCHITECTURE`. Default install dir `C:\Sysinternals`.
- **winget** — `winget install --id Microsoft.Sysinternals`.
  Documents the Server Core caveat.
- **live** — per-binary loop downloading from
  `https://live.sysinternals.com/<binary>`.

All three optionally append an `_accepteula_block` that runs each
known tool once with `-accepteula` to flip the HKCU EULA flag.

## Binary discovery

`binary_locator.find_binary("handle.exe")` resolves a path in this
order:

1. `SYSINTERNALS_MCP_DIR` env var, joined with the requested name.
2. `where.exe <name>` (PATH lookup).
3. Default install paths in order: `C:\Sysinternals\`,
   `C:\Tools\Sysinternals\`, `%ProgramFiles%\Sysinternals\`.

The result is cached for the process lifetime. To re-probe after
moving the install, restart the server. `KNOWN_BINARIES` (in
`binary_locator.py`) lists every binary the server knows about,
including each tool's HKCU EULA subkey (some don't match the file
stem — e.g. `autorunsc.exe` → `AutoRuns`, `procmon.exe` → `Process
Monitor`, `tcpvcon.exe` → `TcpView`).

Every live tool that needs a binary calls `find_binary()` first. When
the binary is missing the tool returns a friendly markdown error
naming the env var override, the bootstrap tool, and the download URL
— it never raises.

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
- Honors `SYSINTERNALS_MCP_ACCEPT_EULA=1` for `bootstrap_sysinternals`
  consent suppression — see Bootstrap above.

The probe targets `HKCU` (the current user) by default; the
`accept_sysinternals_eula(scope="machine")` tool emits HKLM script
with an explicit "requires elevated PowerShell" note.

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
- **Non-tool modules must not mention LabLink by name** — the
  zero-coupling test scans every `src/sysinternals_mcp/*.py` except
  `tools/*.py` and `app.py`. Use "remote-execution transport" or
  "operator" in those modules.

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
- **`lablink_first_remote_block()` is the canonical remote-dispatch
  helper.** Don't add new tools that re-implement the markdown
  shape; route through the helper so the JSON sidecar + recommended
  transport order stay consistent across the suite.
