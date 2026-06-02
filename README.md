# sysinternals-mcp

An [MCP](https://modelcontextprotocol.io/) server that wraps the Microsoft
Sysinternals tool suite so AI coding assistants can drive Windows process
introspection, binary triage, and ACL audit through natural-language
prompts. Built on FastMCP, Python 3.11+, Windows-first.

This server **ships zero Sysinternals binaries**. You download the
Sysinternals Suite yourself from
<https://learn.microsoft.com/en-us/sysinternals/> and point the server at
your install directory.

## What it can do

| Group         | Tools                                                                                                              |
| ------------- | ------------------------------------------------------------------------------------------------------------------ |
| Setup         | `check_sysinternals_setup`                                                                                         |
| Bootstrap     | `bootstrap_sysinternals`, `accept_sysinternals_eula`                                                               |
| Handles       | `handle_list`, `parse_handle_output`                                                                               |
| Binaries      | `sigcheck`, `parse_sigcheck_output`                                                                                |
| Processes     | `pslist`, `parse_pslist_output`, `psinfo`, `parse_psinfo_output`, `listdlls`, `parse_listdlls_output`              |
| ACLs          | `accesschk`, `parse_accesschk_output`                                                                              |
| Network       | `tcpvcon`, `parse_tcpvcon_output`                                                                                  |
| Autostart     | `autoruns`, `parse_autoruns_output`                                                                                |
| CPU info      | `coreinfo`, `parse_coreinfo_output`                                                                                |
| Crash dumps   | `procdump`, `parse_procdump_output`                                                                                |
| Strings       | `strings`, `parse_strings_output`                                                                                  |
| ProcMon       | `list_procmon_recipes`, `get_procmon_recipe`, `get_procmon_capture_commands`, `get_capture_instructions`, `analyze_pml` |
| Federation    | `get_evidence_status`, `get_entities`                                                                              |

Every live-execute tool takes a `target` argument:

- `target="local"` — the server runs the Sysinternals binary as a
  subprocess on the local machine and returns the parsed markdown.
- `target="remote"` — the server returns a *LabLink-first dispatch*
  block: a fenced ```powershell``` command, a recommended transport
  order (LabLink → PSRemoting → manual paste), and a JSON sidecar an
  LLM can hand straight to any MCP that actually has remote-exec
  tools. You run the command on the remote target, then pipe the
  captured stdout back into the matching `parse_<tool>_output` tool.
  Nothing in `sysinternals-mcp` is coupled to any particular
  remote-execution MCP — see [Remote workflows](#remote-workflows)
  below.

## Install (Windows)

### 1. Get the Sysinternals Suite

The fastest path is the new **bootstrap** tool — see
[Bootstrap install](#bootstrap-install) below. If you prefer to install
manually, download `SysinternalsSuite.zip` from
<https://learn.microsoft.com/en-us/sysinternals/downloads/sysinternals-suite>
and extract it. The default location this server probes is
`C:\Sysinternals`, but you can put it anywhere — see
[Configuration](#configuration).

### 2. Pre-accept the EULAs

Every Sysinternals binary prompts for EULA acceptance on first run.
Without acceptance the binary writes nothing to stdout and the MCP
tools cannot parse output. After install, run `check_sysinternals_setup`
once — for any tool with `EULA accepted? = no` the tool returns the
exact `reg add` command you need to run to pre-accept under the current
user account. Re-run `check_sysinternals_setup` to confirm.

Alternatively call `accept_sysinternals_eula(scope="user")` once and
the MCP will return the full reg-add script for every known tool. Or
run each tool once with `-accepteula` (the server passes that flag on
every invocation anyway; the only purpose of pre-accepting is to make
the registry probe report a clean state).

### 3. Install the MCP server

```powershell
# Install uv if you have not already.
winget install astral-sh.uv

# Clone + run from source for now.
git clone https://github.com/nijosmsft/sysinternals-mcp C:\git\sysinternals-mcp
cd C:\git\sysinternals-mcp
uv sync
```

### 4. Wire it into your MCP client

```json
{
  "mcpServers": {
    "sysinternals": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "C:\\git\\sysinternals-mcp",
               "python", "-m", "sysinternals_mcp.server"],
      "env": {
        "SYSINTERNALS_MCP_DIR": "C:\\Sysinternals"
      }
    }
  }
}
```

The top-level key is `mcpServers` for Claude Code / Claude Desktop /
Cursor / Copilot CLI, and `servers` for VS Code GitHub Copilot.

## Bootstrap install

The `bootstrap_sysinternals` tool is the v0.2 headline feature — it
lets an LLM walk the user through installing the suite without leaving
the chat.

```text
bootstrap_sysinternals(target="local",
                       install_method="zip",     # or "winget" or "live"
                       install_dir="C:\\Sysinternals")
```

The first call returns a **CONSENT REQUIRED** block asking the user to
accept the Sysinternals EULA — the LLM is expected to read it to the
user verbatim. After the user answers, the LLM re-invokes the tool
with `accept_eula=True` to receive the actual install script.

Three install methods:

- **zip** — `Invoke-WebRequest` on `SysinternalsSuite.zip` (auto-picks
  ARM64 build via `$env:PROCESSOR_ARCHITECTURE`), `Expand-Archive` to
  `install_dir`.
- **winget** — `winget install --id Microsoft.Sysinternals` (not
  available on Windows Server Core).
- **live** — per-binary `Invoke-WebRequest` from
  `https://live.sysinternals.com/<binary>`. Useful for restricted
  networks that allow only HTTPS GET.

Bypass the prompt for a whole session by setting
`SYSINTERNALS_MCP_ACCEPT_EULA=1` on the server before launch.

## Configuration

| Env var                          | Purpose                                                                                                 |
| -------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `SYSINTERNALS_MCP_DIR`           | Directory containing the Sysinternals binaries. Searched first; falls back to PATH and default paths.   |
| `SYSINTERNALS_MCP_ACCEPT_EULA`   | Set to `1` to pre-accept the EULA at server startup — `bootstrap_sysinternals` skips the consent block. |
| `SYSINTERNALS_MCP_EVIDENCE_PATH` | (Optional) Root for the per-machine `evidence.duckdb`. Enables `get_entities` when the lib is present.  |

When `SYSINTERNALS_MCP_DIR` is unset the server probes (in order):

1. Each tool's name on `PATH` via `where.exe`.
2. `C:\Sysinternals\`
3. `C:\Tools\Sysinternals\`
4. `%ProgramFiles%\Sysinternals\`

The probe is cached at process start. If you move the install while the
server is running, restart the server.

## Remote workflows

`sysinternals-mcp` is transport-agnostic but **opinionated about
LabLink**: every `target="remote"` tool emits a recommended-dispatch
order with LabLink first, plus a JSON sidecar that an LLM can hand
straight to LabLink's `lablink.execute_command`. The pattern is:

1. Call the live tool with `target="remote"` to get the dispatch
   block (markdown + JSON sidecar).
2. Run the command on the remote machine via your transport of choice
   — LabLink, PowerShell remoting, manual paste.
3. Pipe the stdout back into the matching `parse_<tool>_output` tool
   (the `parse_with` field in the JSON sidecar tells the LLM which).

Example transports — pick whichever fits your environment:

- **LabLink (recommended)**

  ```text
  lablink.execute_command(node="<name>",
                          command="C:\\Sysinternals\\handle.exe -accepteula -p chrome",
                          shell="powershell",
                          timeout=120)
  ```

- **PowerShell remoting**

  ```powershell
  Invoke-Command -ComputerName <host> -ScriptBlock {
      C:\Sysinternals\handle.exe -accepteula -p chrome
  } | Set-Content C:\local\out.txt
  ```

- **Manual / RDP / scp**

  Copy-paste the command, capture the output, paste it back.

The ProcMon workflow follows the same shape:
`get_capture_instructions(target="remote", ...)` returns a full runbook
that includes the start / wait / stop commands plus three example
transports for pulling the resulting `.pml` back.

## ProcMon recipes

Three bundled filter recipes:

- `file_io_only` — file system activity for the target process(es)
- `network_only` — TCP/UDP send + receive
- `process_lifecycle` — process/thread create + exit

Each recipe is a small text descriptor. **As of v0.2** the descriptor
rules are translated into ProcMon `/Filter` CLI arguments and spliced
into the capture command line directly — no manual
**File → Import Configuration** step is required. See `ASSUMPTIONS.md`
A2 for details.

## Local development

```powershell
# Run the server (stdio — exits on EOF, Ctrl+C to stop interactively).
uv run python -m sysinternals_mcp.server

# Tests — synthetic fixtures, no Sysinternals binaries required, fast.
uv run --group dev pytest tests/ -v
```

## License

MIT. See [LICENSE](LICENSE).

The Sysinternals binaries themselves are governed by the Sysinternals
license — they are **not** redistributed by this project.
