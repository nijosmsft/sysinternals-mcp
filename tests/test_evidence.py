"""Tests for the evidence-store federation hook."""

from __future__ import annotations

from pathlib import Path

import pytest

from sysinternals_mcp import evidence_integration as ev
from sysinternals_mcp.tools.evidence import get_entities, get_evidence_status


def test_status_when_neither_gate_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ev.EVIDENCE_ENV_VAR, raising=False)

    out = get_evidence_status()

    assert "Inactive" in out
    assert "G1" in out
    assert "G2" in out


def test_status_when_only_env_var_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ev.EVIDENCE_ENV_VAR, str(tmp_path))

    out = get_evidence_status()

    # Without the optional library installed, gate G1 is missing and
    # the federation is still inactive.
    if ev.is_available():
        assert "Active" in out
    else:
        assert "Inactive" in out
        assert str(tmp_path) in out  # G2 detail still shown


def test_get_entities_unknown_type() -> None:
    out = get_entities(entity_type="bogus")
    assert "Unknown entity_type" in out


def test_get_entities_returns_noop_when_inactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ev.EVIDENCE_ENV_VAR, raising=False)

    out = get_entities(entity_type="machine")

    assert "inactive" in out.lower()


def test_register_local_machine_noop_without_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ev.EVIDENCE_ENV_VAR, raising=False)
    assert ev.register_local_machine() is None


def test_both_gates_helpers_consistent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ev.EVIDENCE_ENV_VAR, raising=False)
    assert ev.is_configured() is False
    assert ev.both_gates_open() is False
    assert ev.evidence_root() is None


def test_db_path_for_when_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ev.EVIDENCE_ENV_VAR, str(tmp_path))

    p = ev.db_path_for("host1")

    assert p is not None
    assert p.parent == tmp_path
    assert p.name == "host1.sqlite"
