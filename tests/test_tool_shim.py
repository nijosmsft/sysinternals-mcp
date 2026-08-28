"""FastMCP 1.x -> 2.x compatibility shim.

The ``_SysinternalsFastMCP.tool`` override must register the tool with the
server (the side effect) yet hand back the *original* callable for every call
form, matching the fleet-standard subclass pattern used by etw-mcp
(``_EtwFastMCP``), perfmon (``_PerfmonFastMCP``), and razzle
(``_RazzleFastMCP``). FastMCP 2.x's stock decorator otherwise returns a
non-callable ``FunctionTool``.
"""

from __future__ import annotations

from sysinternals_mcp.app import _SysinternalsFastMCP


def _registered_names(mcp: _SysinternalsFastMCP) -> list[str]:
    """Every tool name registered on ``mcp`` (list, so duplicates show)."""
    tool_mgr = getattr(mcp, "_tool_manager", None)
    if tool_mgr is not None:
        inner = getattr(tool_mgr, "_tools", None)
        if inner is None:
            inner = getattr(tool_mgr, "tools", None)
        if isinstance(inner, dict):
            return list(inner.keys())
    for attr in ("_tools", "tools"):
        candidate = getattr(mcp, attr, None)
        if isinstance(candidate, dict):
            return list(candidate.keys())
    raise AssertionError("could not locate the FastMCP tool registry")


def test_bare_decorator_returns_original_callable() -> None:
    """``@mcp.tool`` (function passed directly to the decorator)."""
    mcp = _SysinternalsFastMCP("shim-test-bare")

    @mcp.tool
    def bare_tool(x: int) -> int:
        return x + 1

    assert callable(bare_tool)
    assert bare_tool(41) == 42
    assert _registered_names(mcp).count("bare_tool") == 1


def test_factory_decorator_returns_original_callable() -> None:
    """``@mcp.tool(...)`` factory form returning a decorator."""
    mcp = _SysinternalsFastMCP("shim-test-factory")

    @mcp.tool(name="renamed_tool")
    def factory_tool(x: int) -> int:
        return x * 2

    assert callable(factory_tool)
    assert factory_tool(21) == 42
    # Registered under the supplied name, exactly once.
    assert _registered_names(mcp).count("renamed_tool") == 1


def test_bare_direct_call_returns_original_callable() -> None:
    """``mcp.tool(fn)`` invoked directly, not as a decorator."""
    mcp = _SysinternalsFastMCP("shim-test-direct")

    def direct_tool(x: int) -> int:
        return x - 1

    result = mcp.tool(direct_tool)

    assert result is direct_tool
    assert callable(result)
    assert result(43) == 42
    assert _registered_names(mcp).count("direct_tool") == 1


def test_all_forms_register_exactly_once() -> None:
    """No form double-registers; three distinct tools land on one server."""
    mcp = _SysinternalsFastMCP("shim-test-all")

    @mcp.tool
    def form_bare() -> str:
        return "bare"

    @mcp.tool(name="form_factory")
    def _form_factory() -> str:
        return "factory"

    def _form_direct() -> str:
        return "direct"

    mcp.tool(_form_direct)

    names = _registered_names(mcp)
    for expected in ("form_bare", "form_factory", "_form_direct"):
        assert names.count(expected) == 1, f"{expected}: {names.count(expected)}"
