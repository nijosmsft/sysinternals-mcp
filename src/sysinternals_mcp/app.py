"""FastMCP application instance — imported by all tool modules."""

from fastmcp import FastMCP


class _SysinternalsFastMCP(FastMCP):
    """FastMCP whose ``@tool()`` returns the original function.

    FastMCP 2.x replaces a decorated function with a non-callable
    ``FunctionTool`` object, whereas the ``mcp.server.fastmcp`` 1.x decorator
    returned the underlying function untouched. Every tool module here (and the
    test-suite) relies on that 1.x behaviour: the ``target='remote'`` wrappers
    and ``parse_*`` helpers call the decorated ``@mcp.tool()`` functions
    straight through, and the tests invoke the decorated callables directly.
    Overriding ``tool`` to register with the server (the side effect) and then
    hand back the original function preserves that contract while still running
    on the standalone fastmcp package.
    """

    def tool(self, *args, **kwargs):
        # ``@mcp.tool`` (bare decorator) and ``mcp.tool(fn)`` (bare direct
        # call): a single positional callable and no name/kwargs.
        if len(args) == 1 and callable(args[0]) and not kwargs:
            super().tool(args[0])
            return args[0]

        # ``@mcp.tool(...)`` factory form. Register via the bare form
        # (``super().tool(fn, **opts)``) rather than ``super().tool(**opts)(fn)``:
        # the latter returns a partial re-bound to this overridden ``tool``, which
        # never actually registers the function with the server.
        def decorator(fn):
            super(_SysinternalsFastMCP, self).tool(fn, *args, **kwargs)
            return fn

        return decorator


mcp = _SysinternalsFastMCP(
    "sysinternals-mcp",
    instructions=(
        "Wrap the Microsoft Sysinternals tool suite for Windows process "
        "introspection, binary triage, ACL audit, and event-trace capture. "
        "v0.2 ships ~32 tools across 11 Sysinternals binaries plus a "
        "bootstrap installer.\n"
        "\n"
        "SETUP: if Sysinternals isn't installed on the target, call "
        "`bootstrap_sysinternals(target, install_method='zip'|'winget'|"
        "'live')`. The first call returns a CONSENT REQUIRED block "
        "asking the user to accept the Sysinternals EULA -- read it to "
        "them verbatim. After they answer, re-invoke with "
        "`accept_eula=True` (Yes) or call `accept_sysinternals_eula"
        "(scope='user'|'machine')` separately. Setting the env var "
        "`SYSINTERNALS_MCP_ACCEPT_EULA=1` on the server suppresses the "
        "prompt for the whole session.\n"
        "\n"
        "Already installed? Call `check_sysinternals_setup` to confirm "
        "every binary resolves and each EULA flag is set under the "
        "current user.\n"
        "\n"
        "LIVE TOOLS: `handle_list`, `sigcheck`, `pslist`, `accesschk`, "
        "`tcpvcon`, `autoruns`, `coreinfo`, `psinfo`, `listdlls`, "
        "`procdump`, `strings`. Each takes `target='local'` (server "
        "runs the binary as a subprocess) or `target='remote'` (server "
        "returns a *LabLink-first dispatch* block: a recommended "
        "transport order plus a JSON sidecar an LLM can hand straight "
        "to a remote-exec MCP). For remote runs, capture stdout and "
        "pipe it into the matching `parse_<tool>_output` tool to "
        "render identical markdown.\n"
        "\n"
        "REMOTE INTEGRATION IDIOM: every `target='remote'` block "
        "recommends LabLink (`lablink.execute_command`) as the "
        "preferred dispatch, then PSRemoting, then manual paste. The "
        "JSON sidecar contains `command`, `shell`, `timeout_s`, "
        "`expected_runtime_s`, and `parse_with` -- enough for an LLM "
        "to dispatch and then immediately re-parse.\n"
        "\n"
        "PROCMON CAPTURE: `list_procmon_recipes` for bundled filters "
        "(file_io_only / network_only / process_lifecycle). "
        "`get_procmon_recipe(recipe)` for contents. "
        "`get_procmon_capture_commands(recipe, output_path, duration_s)` "
        "for the 3-step start/sleep/stop commands. v0.2 closes the "
        "v0.1 deferral: filter rules from the .pmcx descriptor are "
        "translated into `/Filter` CLI args and spliced into the "
        "command line inline -- no GUI step required. "
        "`get_capture_instructions(recipe, target, output_path)` for "
        "the long-form runbook.\n"
        "\n"
        "PML ANALYSIS: `analyze_pml(path)` decodes a ProcMon .pml file "
        "by shelling out to procmon.exe /OpenLog /SaveAs CSV then "
        "summarizing with pandas (top processes, op-class histogram, "
        "error count).\n"
        "\n"
        "FEDERATION: `get_evidence_status` and `get_entities` are no-ops "
        "by default. Enable by installing the optional `evidence-store` "
        "library AND setting `SYSINTERNALS_MCP_EVIDENCE_PATH`.\n"
        "\n"
        "REMOTE-AGNOSTIC: NOTHING in this MCP imports any specific "
        "remote-execution MCP. LabLink is named as a *recommended* "
        "transport in tool output, alongside PSRemoting and manual "
        "paste. The server keeps zero coupling -- enforced by test."
    ),
)
