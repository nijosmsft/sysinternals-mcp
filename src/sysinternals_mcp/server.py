"""Sysinternals MCP Server.

Provides MCP tools that wrap the Microsoft Sysinternals tool suite for
Windows process introspection, binary triage, ACL audit, and event-trace
capture. The server ships zero Sysinternals binaries — the operator
downloads them and points the server at the install dir via the
``SYSINTERNALS_MCP_DIR`` env var.
"""

from sysinternals_mcp.app import mcp  # noqa: F401 — re-export

# Register all tool modules — each module calls @mcp.tool() on import.
# If you add a new module, add the import here or its tools will not be
# visible to MCP clients.
import sysinternals_mcp.tools.setup  # noqa: F401, E402
import sysinternals_mcp.tools.handle  # noqa: F401, E402
import sysinternals_mcp.tools.sigcheck  # noqa: F401, E402
import sysinternals_mcp.tools.pslist  # noqa: F401, E402
import sysinternals_mcp.tools.accesschk  # noqa: F401, E402
import sysinternals_mcp.tools.procmon  # noqa: F401, E402
import sysinternals_mcp.tools.tcpvcon  # noqa: F401, E402  — v0.2
import sysinternals_mcp.tools.autoruns  # noqa: F401, E402  — v0.2
import sysinternals_mcp.tools.evidence  # noqa: F401, E402  — optional evidence-store federation hook


def main() -> None:
    """Entry point — runs the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
