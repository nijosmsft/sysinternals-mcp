"""ProcMon-related MCP tools.

Five tools wrap ProcMon end to end:

- ``list_procmon_recipes`` -- enumerate shipped recipes.
- ``get_procmon_recipe`` -- return the recipe's text descriptor.
- ``get_procmon_capture_commands`` -- build the procmon.exe command
  line for a capture (target='local' or 'remote').
- ``get_capture_instructions`` -- long-form runbook for an operator
  running the capture themselves (includes transfer-back guidance
  for remote targets, naming PSRemoting, an MCP exec transport such
  as LabLink, and manual SMB/SCP as three independent options).
- ``analyze_pml`` -- given a local ``.pml`` path, summarize.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from sysinternals_mcp.app import mcp
from sysinternals_mcp.formatting.markdown import format_table
from sysinternals_mcp.parsing.pml_parser import analyze_pml_file
from sysinternals_mcp.parsing.procmon_filter import (
    parse_pmcx_text,
    rules_to_cli_args,
)
from sysinternals_mcp.profiles.metadata import (
    RECIPES,
    RecipeMeta,
    get_recipe,
    list_recipes,
    load_descriptor_text,
)
from sysinternals_mcp.tools._common import (
    ToolError,
    remote_command_block,
    require_binary,
    validate_target,
)

_TOOL = "procmon.exe"


@mcp.tool()
def list_procmon_recipes() -> str:
    """List shipped ProcMon recipes (filter presets)."""
    df = pd.DataFrame(
        [
            {
                "Recipe": r.recipe,
                "Title": r.title,
                "When to use": r.when_to_use,
                "Volume": r.est_volume,
            }
            for r in list_recipes()
        ]
    )
    return (
        f"**ProcMon recipes** ({len(df)} available)\n\n"
        + format_table(df, max_rows=20)
        + "\n\n"
        "Use `get_procmon_recipe(recipe='<name>')` for the full "
        "text descriptor, or `get_procmon_capture_commands(...)` "
        "for the procmon.exe command line.\n"
    )


def _render_recipe(meta: RecipeMeta) -> str:
    descriptor = load_descriptor_text(meta)
    return (
        f"# ProcMon recipe: `{meta.recipe}` -- {meta.title}\n"
        "\n"
        f"**When to use**: {meta.when_to_use}\n"
        "\n"
        f"**Filter**: {meta.filter_description}\n"
        "\n"
        f"**Privilege**: {meta.privilege}\n"
        "\n"
        f"**Volume estimate**: {meta.est_volume}\n"
        "\n"
        f"**Notes**: {meta.notes}\n"
        "\n"
        f"## Text descriptor (`{meta.descriptor_filename}`)\n"
        "\n"
        "```text\n"
        f"{descriptor.rstrip()}\n"
        "```\n"
    )


@mcp.tool()
def get_procmon_recipe(recipe: str) -> str:
    """Return the text descriptor for a recipe.

    Args:
        recipe: Recipe short name (see ``list_procmon_recipes``).
    """
    meta = get_recipe(recipe)
    if meta is None:
        valid = ", ".join(sorted(RECIPES))
        return f"Unknown recipe `{recipe}`. Valid: {valid}."
    return _render_recipe(meta)


def _capture_cmdline(
    procmon: str,
    recipe: str,
    output_path: str,
    duration_s: int,
    filter_args: list[str] | None = None,
) -> list[str]:
    cmd: list[str] = [
        procmon,
        "/AcceptEula",
        "/Quiet",
        "/Minimized",
    ]
    if filter_args:
        cmd.extend(filter_args)
    cmd.extend(
        [
            "/BackingFile",
            output_path,
            "/Runtime",
            str(duration_s),
        ]
    )
    return cmd


@mcp.tool()
def get_procmon_capture_commands(
    recipe: str,
    output_path: str = r"C:\procmon\out.pml",
    duration_s: int = 60,
    target: str = "local",
) -> str:
    """Build the ``procmon.exe`` command to capture a trace.

    v0.2: the recipe's ``[Includes]`` / ``[Excludes]`` rules from the
    ``.pmcx`` descriptor are translated to ``/Filter`` CLI args inline,
    so no binary ``.pmc`` and no GUI step is required to apply the
    filter. The previous ``/LoadConfig`` workflow (a deferral noted in
    ASSUMPTIONS A2) is now optional -- it remains documented for
    operators who already maintain a curated ``.pmc``.

    Args:
        recipe: Recipe short name (see ``list_procmon_recipes``).
        output_path: Destination ``.pml`` path on the capture machine.
        duration_s: Capture duration in seconds. ProcMon stops itself
            when ``/Runtime`` elapses.
        target: ``"local"`` resolves the local procmon.exe;
            ``"remote"`` emits a paste-ready command for another host
            (uses the bare ``procmon.exe`` name).
    """
    err = validate_target(target)
    if err is not None:
        return err
    meta = get_recipe(recipe)
    if meta is None:
        valid = ", ".join(sorted(RECIPES))
        return f"Unknown recipe `{recipe}`. Valid: {valid}."

    procmon = "procmon.exe"
    if target == "local":
        binary = require_binary(_TOOL)
        if isinstance(binary, str):
            return binary
        procmon = str(binary)

    # v0.2: parse the .pmcx descriptor into /Filter args.
    descriptor_text = load_descriptor_text(meta)
    rules = parse_pmcx_text(descriptor_text)
    filter_args = rules_to_cli_args(rules)

    cmdline = _capture_cmdline(
        procmon, recipe, output_path, duration_s, filter_args=filter_args
    )
    inc_count = sum(1 for r in rules if r.include)
    exc_count = sum(1 for r in rules if not r.include)
    filter_note = (
        f"Filter rules applied inline via `/Filter`: "
        f"{inc_count} Include + {exc_count} Exclude "
        f"(from `{meta.descriptor_filename}`). "
        f"No GUI step or `.pmc` file is required."
    )
    pmc_note = (
        "Optional: if you already maintain a binary `.pmc` for this "
        f"host, you can add `/LoadConfig <path>.pmc` instead. The "
        "rules emitted here are equivalent to the descriptor "
        f"`{meta.descriptor_filename}`."
    )
    header = (
        f"**Capture command -- recipe `{recipe}`, target=`{target}`**\n"
        "\n"
        f"Duration: {duration_s}s. Output: `{output_path}`.\n"
        "\n"
        f"{filter_note}\n"
        "\n"
    )
    return header + remote_command_block(cmdline, note=pmc_note) + "\n"


@mcp.tool()
def get_capture_instructions(
    recipe: str,
    target: str = "local",
    output_path: str = r"C:\procmon\out.pml",
    duration_s: int = 60,
) -> str:
    """Long-form runbook for capturing + analyzing a ProcMon trace.

    For ``target='remote'`` the runbook calls out three independent
    options for shipping ProcMon to the remote host and pulling the
    .pml back: PSRemoting (built into Windows), an MCP exec transport
    such as LabLink (or any equivalent), and manual SMB / scp. This
    server has zero coupling to any specific transport.
    """
    err = validate_target(target)
    if err is not None:
        return err
    meta = get_recipe(recipe)
    if meta is None:
        valid = ", ".join(sorted(RECIPES))
        return f"Unknown recipe `{recipe}`. Valid: {valid}."

    capture_cmd = get_procmon_capture_commands(
        recipe=recipe,
        output_path=output_path,
        duration_s=duration_s,
        target=target,
    )

    if target == "local":
        return (
            f"# Local ProcMon capture runbook -- `{recipe}`\n"
            "\n"
            f"## 1. Verify install\n"
            "\n"
            "Run `check_sysinternals_setup` first.\n"
            "\n"
            f"## 2. Run the capture\n"
            "\n"
            "v0.2: the recipe's filter set is applied inline via "
            "`/Filter` args, so no GUI step or `.pmc` file is needed.\n"
            "\n"
            + capture_cmd
            + "\n"
            f"## 3. Analyze\n"
            "\n"
            f"After ProcMon exits, call "
            f"`analyze_pml(path='{output_path}')` to get a markdown "
            "summary.\n"
        )

    # target == "remote"
    return (
        f"# Remote ProcMon capture runbook -- `{recipe}`\n"
        "\n"
        "This server runs entirely on the operator's machine. To "
        "capture on a remote target, ship `procmon.exe` to that host, "
        "run the capture, and pull the resulting `.pml` back here for "
        "`analyze_pml`. The transport is up to you -- three "
        "independent options, in recommended order:\n"
        "\n"
        "- **[LabLink](https://github.com/nijosmsft/LabLink) "
        "(recommended)**: an MCP exec transport that "
        "exposes `push_file` / `execute_command` / `pull_file`. The "
        "JSON sidecar block emitted by `get_procmon_capture_commands` "
        "can be passed straight to `lablink.execute_command(node=..., "
        "...)`. This server has no Python dependency on LabLink -- "
        "it just emits the dispatch payload.\n"
        "- **PSRemoting**: `Copy-Item -ToSession`, "
        "`Invoke-Command -ScriptBlock`. Built into Windows. Useful "
        "when LabLink isn't deployed.\n"
        "- **Manual**: `\\\\<host>\\C$\\Sysinternals\\` SMB copy or "
        "`scp` / `rsync` over SSH.\n"
        "\n"
        f"## 1. Stage procmon.exe on the remote host\n"
        "\n"
        f"Copy `procmon.exe` (and `procmon64.exe` if 64-bit) to "
        f"`C:\\Sysinternals\\` on the target. With LabLink: "
        "`lablink.push_file(...)`.\n"
        "\n"
        f"## 2. Run the capture\n"
        "\n"
        "v0.2: the recipe's filter set is baked into the command "
        "below as `/Filter` args -- no GUI step needed.\n"
        "\n"
        + capture_cmd
        + "\n"
        f"## 3. Pull the .pml back\n"
        "\n"
        f"With LabLink: `lablink.pull_file(node, remote='{output_path}', "
        "local='<your local path>')`. With PSRemoting: "
        "`Copy-Item -FromSession`. With manual: SMB / scp.\n"
        "\n"
        f"## 4. Analyze\n"
        "\n"
        f"`analyze_pml(path='<local copy of .pml>')` summarizes the "
        "trace -- top processes, event-class histogram, error "
        "count.\n"
    )


def _render_summary(summary, pml_path: str, top_n: int) -> str:
    if summary.total_rows == 0:
        return (
            f"*No events in `{pml_path}`.* "
            "ProcMon may have been started with an over-aggressive "
            "filter, or the capture ran for too short a time."
        )
    return (
        f"**ProcMon summary `{pml_path}`** "
        f"({summary.total_rows:,} events, "
        f"{summary.error_count:,} non-success results)\n\n"
        f"**Top {top_n} processes**\n\n"
        + format_table(summary.top_processes, max_rows=top_n)
        + "\n\n**Event class histogram**\n\n"
        + format_table(summary.op_class_counts)
        + "\n\n*CSV columns extracted: "
        f"{', '.join(f'`{c}`' for c in summary.columns)}.*\n"
    )


@mcp.tool()
def analyze_pml(path: str, top_n: int = 20) -> str:
    """Summarize a ``.pml`` trace produced by ProcMon.

    Internally shells `procmon.exe /OpenLog ... /SaveAs ... /Quiet` to
    convert to CSV, then reads with pandas. Requires `procmon.exe` to
    be locatable (see ``check_sysinternals_setup``).

    Args:
        path: Local filesystem path to the ``.pml`` file.
        top_n: Number of top processes to surface (default 20).
    """
    if not path or not path.strip():
        return "`path` must be a non-empty path to a `.pml` file."
    pml_path = Path(path)
    if not pml_path.exists():
        return f"`{path}` does not exist on this machine."
    if pml_path.suffix.lower() != ".pml":
        return (
            f"`{path}` does not look like a `.pml` file. "
            "ProcMon traces use the `.pml` extension."
        )

    binary = require_binary(_TOOL)
    if isinstance(binary, str):
        return binary

    try:
        summary = analyze_pml_file(binary, pml_path, top_n=top_n)
    except (RuntimeError, ToolError, FileNotFoundError) as exc:
        return f"**`analyze_pml` failed**: {exc}"

    return _render_summary(summary, str(pml_path), top_n)
