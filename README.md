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

| Group        | Tools                                                                                          |
| ------------ | ---------------------------------------------------------------------------------------------- |
| Setup        | `check_sysinternals_setup`                                                                     |
| Handles      | `handle_list`, `parse_handle_output`                                                           |
| Binaries     | `sigcheck`, `parse_sigcheck_output`                                                            |
| Processes    | `pslist`, `parse_pslist_output`                                                                |
| ACLs         | `accesschk`, `parse_accesschk_output`                                                          |
| ProcMon      | `list_procmon_recipes`, `get_procmon_recipe`, `get_procmon_capture_commands`, `get_capture_instructions`, `analyze_pml` |
| Federation   | `get_evidence_status`, `get_entities`                                                          |

Every live-execute tool takes a `target` argument:

- `target="local"` — the server runs the Sysinternals binary as a
  subprocess on the local machine and returns the parsed markdown.
- `target="remote"` — the server returns the exact command line as a
  fenced ```powershell``` block. You run it on the remote target via any
  transport (PowerShell remoting, an MCP file-transfer tool such as
  LabLink, SSH, or even a human pasting it into an RDP window), then
  hand the captured stdout back to the matching `parse_<tool>_output`
  tool. Nothing in `sysinternals-mcp` is coupled to any particular
  remote-execution MCP — see [Remote workflows](#remote-workflows) below.

## Install (Windows)

### 1. Get the Sysinternals Suite

Download `SysinternalsSuite.zip` from
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

Alternatively run each tool once with `-accepteula` (the server passes
that flag on every invocation anyway; the only purpose of pre-accepting
is to make the registry probe report a clean state).

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

## Configuration

| Env var                          | Purpose                                                                                                 |
| -------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `SYSINTERNALS_MCP_DIR`           | Directory containing the Sysinternals binaries. Searched first; falls back to PATH and default paths.   |
| `SYSINTERNALS_MCP_EVIDENCE_PATH` | (Optional) Root for the per-machine `evidence.duckdb`. Enables `get_entities` when the lib is present.  |

When `SYSINTERNALS_MCP_DIR` is unset the server probes (in order):

1. Each tool's name on `PATH` via `where.exe`.
2. `C:\Sysinternals\`
3. `C:\Tools\Sysinternals\`
4. `%ProgramFiles%\Sysinternals\`

The probe is cached at process start. If you move the install while the
server is running, restart the server.

## Remote workflows

`sysinternals-mcp` is transport-agnostic. The recommended pattern when
you need to inspect a remote machine is:

1. Call the live tool with `target="remote"` to get the command.
2. Run the command on the remote machine via your transport of choice.
3. Pipe the stdout back into the matching `parse_<tool>_output` tool.

Example transports — pick whichever fits your environment:

- **PowerShell remoting**

  ```powershell
  Invoke-Command -ComputerName <host> -ScriptBlock {
      C:\Sysinternals\handle.exe -accepteula -p chrome
  } | Set-Content C:\local\out.txt
  ```

- **LabLink (one example MCP file/exec transport)**

  ```text
  execute_command(node="<name>",
                  command="C:\\Sysinternals\\handle.exe -accepteula -p chrome")
  ```

- **Manual / RDP / scp**

  Copy-paste the command, capture the output, paste it back.

The ProcMon workflow follows the same shape:
`get_capture_instructions(target="remote", ...)` returns a full runbook
that includes the start / wait / stop commands plus three example
transports for pulling the resulting `.pml` back.

## ProcMon recipes

Three bundled filter recipes for v0.1:

- `file_io_only` — file system activity for the target process(es)
- `network_only` — TCP/UDP send + receive
- `process_lifecycle` — process/thread create + exit

Each recipe is a small text descriptor that ProcMon imports via
**File → Import Configuration**. See `ASSUMPTIONS.md` for why v0.1
ships descriptors instead of binary `.pmc` files.

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
