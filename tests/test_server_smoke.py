"""Smoke test: importing the server must register every expected tool."""

from __future__ import annotations


def test_server_import_registers_expected_tools() -> None:
    # Import for side effects: every tools.* module must wire onto the
    # shared FastMCP instance.
    from sysinternals_mcp import server  # noqa: F401

    from sysinternals_mcp.app import mcp

    # FastMCP doesn't expose a stable list_tools() across versions,
    # so peek at the underlying tool manager.
    registered: set[str] = set()
    for attr in ("_tools", "tools"):
        candidate = getattr(mcp, attr, None)
        if isinstance(candidate, dict):
            registered = set(candidate.keys())
            break
    if not registered:
        tool_mgr = getattr(mcp, "_tool_manager", None)
        if tool_mgr is not None:
            inner = getattr(tool_mgr, "_tools", None) or getattr(tool_mgr, "tools", None)
            if isinstance(inner, dict):
                registered = set(inner.keys())

    expected = {
        # v0.1
        "check_sysinternals_setup",
        "handle_list",
        "parse_handle_output",
        "sigcheck",
        "parse_sigcheck_output",
        "pslist",
        "parse_pslist_output",
        "accesschk",
        "parse_accesschk_output",
        "list_procmon_recipes",
        "get_procmon_recipe",
        "get_procmon_capture_commands",
        "get_capture_instructions",
        "analyze_pml",
        "get_evidence_status",
        "get_entities",
        # v0.2 wrappers
        "tcpvcon",
        "parse_tcpvcon_output",
        "autoruns",
        "parse_autoruns_output",
        "coreinfo",
        "parse_coreinfo_output",
        "psinfo",
        "parse_psinfo_output",
        "listdlls",
        "parse_listdlls_output",
        "procdump",
        "parse_procdump_output",
        "strings",
        "parse_strings_output",
        # v0.2 bootstrap UX
        "bootstrap_sysinternals",
        "accept_sysinternals_eula",
    }
    missing = expected - registered
    assert not missing, (
        f"Expected tools not registered: {missing}. "
        f"Registered: {sorted(registered)}"
    )


def test_server_main_callable() -> None:
    from sysinternals_mcp.server import main

    assert callable(main)
