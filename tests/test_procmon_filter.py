"""Tests for sysinternals_mcp.parsing.procmon_filter."""

from __future__ import annotations

from sysinternals_mcp.parsing.procmon_filter import (
    FilterRule,
    parse_pmcx_text,
    rules_to_cli_args,
)


def test_filter_rule_to_cli_arg_include() -> None:
    rule = FilterRule("Operation", "contains", "CreateFile", include=True)
    assert rule.to_cli_arg() == "Operation;contains;CreateFile;Include"


def test_filter_rule_to_cli_arg_exclude() -> None:
    rule = FilterRule("Operation", "contains", "RegOpenKey", include=False)
    assert rule.to_cli_arg() == "Operation;contains;RegOpenKey;Exclude"


def test_parse_pmcx_text_includes_only() -> None:
    text = (
        "# comment\n"
        "[Includes]\n"
        "Operation contains CreateFile\n"
        "Operation contains ReadFile\n"
    )
    rules = parse_pmcx_text(text)
    assert len(rules) == 2
    assert all(r.include for r in rules)
    assert rules[0].value == "CreateFile"
    assert rules[1].value == "ReadFile"


def test_parse_pmcx_text_includes_and_excludes() -> None:
    text = (
        "[Includes]\n"
        "Operation contains CreateFile\n"
        "\n"
        "[Excludes]\n"
        "Operation contains RegOpenKey\n"
        "Operation contains TCP\n"
    )
    rules = parse_pmcx_text(text)
    assert len(rules) == 3
    assert rules[0].include is True
    assert rules[1].include is False
    assert rules[2].include is False
    assert rules[1].value == "RegOpenKey"


def test_parse_pmcx_text_ignores_capture_section() -> None:
    text = (
        "[Includes]\n"
        "Operation contains CreateFile\n"
        "\n"
        "[Capture]\n"
        "BackingFile suggestion: C:\\out.pml\n"
        "Runtime suggestion: 60 seconds\n"
    )
    rules = parse_pmcx_text(text)
    assert len(rules) == 1
    assert rules[0].value == "CreateFile"


def test_parse_pmcx_text_skips_comments_and_blank_lines() -> None:
    text = (
        "# Comment 1\n"
        "\n"
        "[Includes]\n"
        "# Inline comment\n"
        "Operation contains CreateFile\n"
        "\n"
        "Operation contains ReadFile\n"
    )
    rules = parse_pmcx_text(text)
    assert len(rules) == 2


def test_parse_pmcx_text_handles_other_operators() -> None:
    text = (
        "[Includes]\n"
        "Process Name is chrome.exe\n"
        "Path begins with C:\\Windows\n"
    )
    rules = parse_pmcx_text(text)
    assert len(rules) == 2
    assert rules[0].column == "Process Name"
    assert rules[0].op == "is"
    assert rules[0].value == "chrome.exe"
    assert rules[1].op == "begins with"
    assert rules[1].value == "C:\\Windows"


def test_parse_pmcx_text_returns_empty_for_blank_input() -> None:
    assert parse_pmcx_text("") == []
    assert parse_pmcx_text("# only a comment\n") == []


def test_rules_to_cli_args_flattens() -> None:
    rules = [
        FilterRule("Operation", "contains", "CreateFile", include=True),
        FilterRule("Operation", "contains", "RegOpenKey", include=False),
    ]
    args = rules_to_cli_args(rules)
    assert args == [
        "/Filter",
        "Operation;contains;CreateFile;Include",
        "/Filter",
        "Operation;contains;RegOpenKey;Exclude",
    ]


def test_rules_to_cli_args_empty() -> None:
    assert rules_to_cli_args([]) == []


def test_shipped_recipes_all_parse_to_nonempty_rules() -> None:
    """Every shipped recipe must produce at least one filter rule."""
    from sysinternals_mcp.profiles.metadata import (
        list_recipes,
        load_descriptor_text,
    )

    for meta in list_recipes():
        text = load_descriptor_text(meta)
        rules = parse_pmcx_text(text)
        assert rules, f"Recipe {meta.recipe} parsed to no rules"
        # Sanity: each rule must yield a non-empty CLI arg.
        for r in rules:
            arg = r.to_cli_arg()
            assert ";" in arg
            assert arg.endswith(("Include", "Exclude"))
