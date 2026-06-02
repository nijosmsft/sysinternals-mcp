"""Parse ``.pmcx`` text descriptors into ProcMon ``/Filter`` CLI args.

ProcMon's ``/Filter`` CLI argument accepts a semicolon-separated rule
of the form::

    /Filter "<Column>;<Operator>;<Value>;<Include|Exclude>"

For example::

    /Filter "Operation;contains;CreateFile;Include"
    /Filter "Operation;contains;RegOpenKey;Exclude"

The shipped ``.pmcx`` files in ``profiles/procmon/`` use a simple
text grammar:

- Lines starting with ``#`` are comments.
- ``[Includes]`` / ``[Excludes]`` / ``[Capture]`` are sections.
- Within ``[Includes]`` and ``[Excludes]``, each rule is
  ``<Column> <op> <Value>`` -- e.g. ``Operation contains CreateFile``.
- The ``[Capture]`` section is informational only (BackingFile /
  Runtime suggestions) and is ignored by this parser.

The output is a list of :class:`FilterRule` dataclasses; the
:func:`rules_to_cli_args` helper converts them to the argv tokens that
``procmon.exe`` understands.

This module closes ASSUMPTIONS A2 (manual GUI step) by making the
``/Filter`` flag the authoritative driver -- no binary ``.pmc`` and no
GUI step is required to apply a recipe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class FilterRule:
    """One ProcMon ``/Filter`` rule.

    Attributes:
        column: ProcMon column name, e.g. ``Operation``, ``Path``,
            ``Process Name``.
        op: ProcMon match operator, e.g. ``contains``, ``is``,
            ``begins with``.
        value: Match value. Must not contain ``;`` -- ProcMon's
            ``/Filter`` CLI parser uses ``;`` as the field separator
            and has no escape syntax, so any embedded semicolon would
            silently corrupt the rule.
        include: ``True`` for an Include rule, ``False`` for Exclude.
    """

    column: str
    op: str
    value: str
    include: bool

    def to_cli_arg(self) -> str:
        """Return the value that follows ``/Filter`` on the command line.

        Note: callers are responsible for ensuring no field contains
        a literal ``;``. :func:`parse_pmcx_text` enforces this at
        recipe-load time; if you construct a :class:`FilterRule`
        directly, do the same check.
        """
        kind = "Include" if self.include else "Exclude"
        return f"{self.column};{self.op};{self.value};{kind}"


# Tokens we recognize as multi-word operators. Order matters -- the
# longest one wins. Every other word in a rule line is treated as the
# column-name prefix or the value-suffix.
_OPERATORS: tuple[str, ...] = (
    "begins with",
    "ends with",
    "less than",
    "more than",
    "contains",
    "excludes",
    "is",
)


def _split_rule_line(line: str) -> FilterRule | None:
    """Parse one ``<column> <op> <value>`` line into a FilterRule.

    Returns ``None`` if the line is blank or no operator is found.
    The ``include`` flag is set by the section context, not the rule
    line itself; callers patch it after parsing.
    """
    stripped = line.strip()
    if not stripped:
        return None
    # Find the operator, longest match first.
    for op in _OPERATORS:
        token = f" {op} "
        idx = stripped.lower().find(token)
        if idx == -1:
            continue
        column = stripped[:idx].strip()
        value = stripped[idx + len(token) :].strip()
        if not column or not value:
            return None
        return FilterRule(
            column=column,
            op=op,
            value=value,
            # Default to Include; section parser flips for Excludes.
            include=True,
        )
    return None


def parse_pmcx_text(text: str) -> list[FilterRule]:
    """Parse the full text of a ``.pmcx`` descriptor into FilterRules.

    Order is preserved: every Include rule appears before any Exclude
    rule in the output list, in the order they appeared inside the
    section. The ``[Capture]`` section is ignored.

    Raises:
        ValueError: when any rule's column or value contains a literal
            ``;``. ProcMon's ``/Filter`` CLI uses ``;`` as a field
            separator with no escape, so a value like ``a;b`` would
            silently produce an invalid rule. Failing fast at recipe-
            load time keeps broken filters from reaching ProcMon.
    """
    if not text:
        return []
    section: str | None = None
    rules: list[FilterRule] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip() if not raw.lstrip().startswith("#") else ""
        stripped = line.strip()
        if not stripped:
            continue
        low = stripped.lower()
        if low.startswith("[") and low.endswith("]"):
            section = low.strip("[]").strip()
            continue
        if section not in {"includes", "excludes"}:
            continue
        rule = _split_rule_line(line)
        if rule is None:
            continue
        if section == "excludes":
            rule = FilterRule(
                column=rule.column,
                op=rule.op,
                value=rule.value,
                include=False,
            )
        # Fail-fast: ProcMon's /Filter argument is semicolon-separated
        # with no escape syntax. Reject any rule whose column or value
        # contains a literal ``;`` -- emitting the rule would silently
        # corrupt the filter on the command line.
        for field_name, field_value in (
            ("column", rule.column),
            ("value", rule.value),
        ):
            if ";" in field_value:
                raise ValueError(
                    f"ProcMon filter rule {field_name}={field_value!r} "
                    f"(column={rule.column!r}, op={rule.op!r}) contains "
                    "a ';' which ProcMon's /Filter CLI parser uses as "
                    "a field separator with no escape syntax. Rewrite "
                    "the rule without semicolons."
                )
        rules.append(rule)
    return rules


def rules_to_cli_args(rules: Iterable[FilterRule]) -> list[str]:
    """Flatten an iterable of FilterRules into ``/Filter <arg>`` tokens.

    The returned list is suitable to splice into a ``procmon.exe``
    command line right before ``/BackingFile``.
    """
    out: list[str] = []
    for rule in rules:
        out.append("/Filter")
        out.append(rule.to_cli_arg())
    return out


__all__ = [
    "FilterRule",
    "parse_pmcx_text",
    "rules_to_cli_args",
]
