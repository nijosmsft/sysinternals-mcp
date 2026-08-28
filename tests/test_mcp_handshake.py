"""Regression test for the mcp SDK v2 / standalone-fastmcp migration.

mcp SDK 2.x removed the bundled ``mcp.server.fastmcp`` module; FastMCP now
ships as the standalone ``fastmcp`` package. These tests lock in that the
server builds on ``fastmcp`` and completes a real MCP initialize +
``tools/list`` handshake, so a future dependency drift that reintroduces the
``ModuleNotFoundError: No module named 'mcp.server.fastmcp'`` crash fails
loudly here.
"""

from __future__ import annotations

import asyncio

import fastmcp

from sysinternals_mcp import server  # noqa: F401 — import side effects register tools
from sysinternals_mcp.app import mcp


def test_app_uses_standalone_fastmcp() -> None:
    # The shared app instance must build on the standalone ``fastmcp``
    # package, not the removed bundled ``mcp.server.fastmcp`` module.
    from sysinternals_mcp import app

    assert isinstance(mcp, fastmcp.FastMCP)

    # The ``FastMCP`` name bound in app.py must resolve to the standalone
    # package, and the shim subclass must inherit from it.
    assert app.FastMCP.__module__.split(".", 1)[0] == "fastmcp"
    base = app._SysinternalsFastMCP.__bases__[0]
    assert base.__name__ == "FastMCP"
    assert base.__module__.split(".", 1)[0] == "fastmcp"


def test_initialize_and_tools_list_handshake() -> None:
    # Drive a real in-memory MCP session (initialize handshake +
    # tools/list) through the FastMCP client transport.
    async def _run() -> list[str]:
        async with fastmcp.Client(mcp) as client:
            tools = await client.list_tools()
            return [t.name for t in tools]

    names = set(asyncio.run(_run()))
    for expected in (
        "handle_list",
        "sigcheck",
        "pslist",
        "accesschk",
        "bootstrap_sysinternals",
    ):
        assert expected in names, f"{expected} missing from {sorted(names)}"
