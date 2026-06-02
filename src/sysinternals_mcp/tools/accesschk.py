"""``accesschk`` and ``parse_accesschk_output`` MCP tools.

``accesschk`` audits ACLs on files, registry keys, services, and more.
The flag set depends on what the operator wants to know -- we map
``access`` modes to common combinations.
"""

from __future__ import annotations

from sysinternals_mcp.app import mcp
from sysinternals_mcp.formatting.markdown import format_table
from sysinternals_mcp.parsing.accesschk_parser import parse_accesschk_text
from sysinternals_mcp.tools._common import (
    ToolError,
    format_subprocess_error,
    remote_command_block,
    require_binary,
    run_subprocess,
    validate_target,
)

_TOOL = "accesschk.exe"

# Access-mode preset -> accesschk flags. ``rw`` is the broadest "who has
# write access" triage view; ``r`` is read-only audit; ``all`` dumps
# every ACE without filtering; ``effective`` includes effective
# permissions (-e); ``reg`` audits a registry key (-k); ``svc`` audits
# a Windows service (-c).
_ACCESS_MODES: dict[str, list[str]] = {
    "rw": ["-w", "-s", "-q"],
    "r": ["-r", "-s", "-q"],
    "all": ["-s", "-q"],
    "effective": ["-e", "-s", "-q"],
    "reg": ["-k", "-w", "-s", "-q"],
    "svc": ["-c", "-w", "-q"],
}


def _flags_for_mode(access: str) -> list[str] | None:
    return _ACCESS_MODES.get(access.lower())


def _build_cmdline(binary: str, path: str, access: str) -> list[str] | str:
    flags = _flags_for_mode(access)
    if flags is None:
        valid = ", ".join(sorted(_ACCESS_MODES))
        return (
            f"Unknown access mode `{access}`. Valid: {valid}. "
            "`rw` = who has write access (default), `r` = read-only "
            "audit, `all` = every ACE, `effective` = effective "
                "permissions, `reg` = registry key (-k), `svc` = service "
                "(-c)."
            )
    return [binary, "-accepteula", "-nobanner", *flags, path]


def _render_output(text: str, path: str, access: str) -> str:
    df = parse_accesschk_text(text)
    if df.empty:
        return (
            f"*No ACL rows parsed for `{path}` (mode=`{access}`).* "
            "Check that the path exists and that accesschk has "
            "permission to read it."
        )
    return (
        f"**accesschk `{path}`** (mode=`{access}`, {len(df):,} rows)\n\n"
        + format_table(df, max_rows=200)
    )


@mcp.tool()
def accesschk(path: str, access: str = "rw", target: str = "local") -> str:
    """Audit ACLs on a file, directory, registry key, or service.

    Args:
        path: Target path. For files / dirs use the file path. For
            registry use ``HKLM\\...`` or ``HKCU\\...`` syntax (pair
            with the ``-k`` flag manually if needed). For services use
            the service short name.
        access: One of ``"rw"`` (who has write access, default),
            ``"r"`` (read-only audit), ``"all"`` (every ACE),
            ``"effective"`` (effective permissions), ``"reg"``
            (registry key audit via ``-k``), ``"svc"`` (Windows
            service audit via ``-c``).
        target: ``"local"`` runs the binary on this machine.
            ``"remote"`` returns the command line for another host.
    """
    err = validate_target(target)
    if err is not None:
        return err
    if not path or not path.strip():
        return "`path` must be non-empty (e.g. `C:\\Windows\\System32`)."

    flags_or_err = _build_cmdline(_TOOL, path, access)
    if isinstance(flags_or_err, str):
        return flags_or_err
    cmdline_template = flags_or_err

    if target == "remote":
        return (
            f"**`accesschk` -- remote target** "
            f"(path=`{path}`, access=`{access}`)\n"
            "\n"
            + remote_command_block(
                cmdline_template,
                note=(
                    "Pipe the captured stdout into "
                    "`parse_accesschk_output(text=...)` to get the same "
                    "markdown shape you would see for `target='local'`."
                ),
            )
            + "\n"
        )

    binary = require_binary(_TOOL)
    if isinstance(binary, str):
        return binary

    real_cmdline = _build_cmdline(str(binary), path, access)
    if isinstance(real_cmdline, str):  # pragma: no cover — handled above
        return real_cmdline
    try:
        result = run_subprocess(real_cmdline, timeout=120)
    except ToolError as exc:
        return f"**`accesschk` failed**: {exc}"

    if result.returncode != 0 and not result.stdout.strip():
        return format_subprocess_error(result, "accesschk.exe")
    return _render_output(result.stdout, path, access)


@mcp.tool()
def parse_accesschk_output(
    text: str,
    path: str = "<from text>",
    access: str = "rw",
) -> str:
    """Parse raw accesschk stdout into the same markdown shape.

    Args:
        text: Raw stdout captured from a remote accesschk invocation.
        path: Cosmetic -- shown in the table header.
        access: Cosmetic -- shown in the table header.
    """
    if not text or not text.strip():
        return "*Empty input.* Pass the raw stdout of `accesschk`."
    return _render_output(text, path, access)
