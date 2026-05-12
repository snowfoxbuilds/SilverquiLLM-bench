"""Tests for TODO item 2: Violation checking in agent_session.

Validates that _check_violations and _snapshot_all_protected functions
are still available in agent_session, and that AgentSession.run_card()
invokes violation checking after strategy execution.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.agent_session import (
    AgentSession,
    _check_violations,
)
from silverquillm.config import AgentConfig, BenchmarkConfig
from silverquillm.strategies import CardRunResult, CardRunStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(**overrides) -> BenchmarkConfig:
    defaults = dict(
        name="test-bench",
        set_code="FDN",
        model_name="test-model",
        model_provider="test-provider",
        max_context=200_000,
        temperature=0.0,
        agent=AgentConfig(
            timeout_per_card=300,
        ),
    )
    defaults.update(overrides)
    return BenchmarkConfig(**defaults)


_SAMPLE_SPEC = {
    "name": "Grizzly Bears",
    "mana_cost": "{1}{G}",
    "type_line": "Creature — Bear",
    "oracle_text": "",
    "power": "2",
    "toughness": "2",
}


@pytest.fixture()
def fake_repo(tmp_path):
    """Create a fake repo root with protected directories."""
    repo = tmp_path / "repo"
    repo.mkdir()
    # Create protected dirs with at least one file each
    for dirname in ("engine", "cards", "tests", "benchmark", "benchmarks", "docs"):
        d = repo / dirname
        d.mkdir()
        (d / "existing.py").write_text(f"# {dirname}\n")
    return repo


@pytest.fixture()
def session(fake_repo):
    """Create a session with a fake card_dir and patched _REPO_ROOT."""
    card_dir = fake_repo / "card_data"
    card_dir.mkdir()
    (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))

    config = _make_config()
    sess = AgentSession(config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir))
    yield sess
    sess.cleanup()


# ---------------------------------------------------------------------------
# _check_violations — still importable and callable
# ---------------------------------------------------------------------------


class TestRunBlindViolationDetection:
    """_check_violations function is still available for violation detection."""

    def test_violation_when_agent_writes_to_docs(self, session, fake_repo):
        """_check_violations detects writes to protected dirs."""
        from silverquillm.agent_session import _snapshot_all_protected
        ws = session.setup_workspace()

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            snapshot = _snapshot_all_protected(fake_repo)
            # Simulate agent writing to protected dir
            (fake_repo / "docs" / "hack.py").write_text("# hacked\n")
            violations = _check_violations(ws, before=snapshot)

        assert violations is not None
        assert len(violations) > 0

    def test_violation_when_agent_modifies_existing_protected_file(self, session, fake_repo):
        """_check_violations detects modifications to protected files."""
        from silverquillm.agent_session import _snapshot_all_protected
        ws = session.setup_workspace()

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            snapshot = _snapshot_all_protected(fake_repo)
            (fake_repo / "tests" / "existing.py").write_text("# modified\n")
            violations = _check_violations(ws, before=snapshot)

        assert violations is not None
        assert len(violations) > 0

    def test_no_violation_when_agent_only_writes_in_workspace(self, session, fake_repo):
        """No violations when agent only writes in workspace."""
        from silverquillm.agent_session import _snapshot_all_protected
        ws = session.setup_workspace()

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            snapshot = _snapshot_all_protected(fake_repo)
            (ws / "card_impl.py").write_text("x = 1\n")
            violations = _check_violations(ws, before=snapshot)

        assert not violations

    def test_violation_records_tokens(self, session, fake_repo):
        """_check_violations returns violation details."""
        from silverquillm.agent_session import _snapshot_all_protected
        ws = session.setup_workspace()

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            snapshot = _snapshot_all_protected(fake_repo)
            (fake_repo / "docs" / "hack.py").write_text("bad\n")
            violations = _check_violations(ws, before=snapshot)

        assert violations is not None
        assert len(violations) > 0


# ---------------------------------------------------------------------------
# run_card — violation checking functions still importable
# ---------------------------------------------------------------------------


class TestRunTestInformedViolationDetection:
    """Violation checking functions remain importable and functional."""

    def _setup_blind(self, ws):
        blind = ws / "card_impl.py"
        blind.write_text("x = 1\n")
        return blind

    def test_violation_on_first_round(self, session, fake_repo):
        """_check_violations detects violations in workspace context."""
        from silverquillm.agent_session import _snapshot_all_protected
        ws = session.setup_workspace()

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            snapshot = _snapshot_all_protected(fake_repo)
            (fake_repo / "docs" / "hack.py").write_text("# hacked\n")
            violations = _check_violations(ws, before=snapshot)

        assert violations is not None
        assert len(violations) > 0

    def test_violation_on_later_round(self, session, fake_repo):
        """Fresh snapshots can detect violations on later rounds."""
        from silverquillm.agent_session import _snapshot_all_protected
        ws = session.setup_workspace()

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            # Round 1: clean
            snapshot1 = _snapshot_all_protected(fake_repo)
            violations1 = _check_violations(ws, before=snapshot1)
            assert not violations1

            # Round 2: violation
            snapshot2 = _snapshot_all_protected(fake_repo)
            (fake_repo / "cards" / "evil.py").write_text("# evil\n")
            violations2 = _check_violations(ws, before=snapshot2)
            assert violations2 is not None
            assert len(violations2) > 0

    def test_no_violation_when_clean(self, session, fake_repo):
        """No violations when protected dirs are untouched."""
        from silverquillm.agent_session import _snapshot_all_protected
        ws = session.setup_workspace()

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            snapshot = _snapshot_all_protected(fake_repo)
            (ws / "card_impl.py").write_text("x = 2\n")
            violations = _check_violations(ws, before=snapshot)

        assert not violations

    def test_violation_returns_impl_path_if_exists(self, session, fake_repo):
        """Violations are detected even when card_impl.py exists."""
        from silverquillm.agent_session import _snapshot_all_protected
        ws = session.setup_workspace()

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            snapshot = _snapshot_all_protected(fake_repo)
            (ws / "card_impl.py").write_text("x = 1\n")
            (fake_repo / "docs" / "hack.md").write_text("# hacked\n")
            violations = _check_violations(ws, before=snapshot)

        assert violations is not None
        assert (ws / "card_impl.py").exists()

    def test_violation_takes_snapshot_each_round(self, session, fake_repo):
        """Fresh snapshots each round prevent false positives."""
        from silverquillm.agent_session import _snapshot_all_protected
        ws = session.setup_workspace()

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            # Round 1: clean
            snapshot1 = _snapshot_all_protected(fake_repo)
            (ws / "card_impl.py").write_text("x = 1\n")
            violations1 = _check_violations(ws, before=snapshot1)
            assert not violations1

            # Round 2: also clean (different snapshot)
            snapshot2 = _snapshot_all_protected(fake_repo)
            (ws / "card_impl.py").write_text("x = 2\n")
            violations2 = _check_violations(ws, before=snapshot2)
            assert not violations2


# ---------------------------------------------------------------------------
# run_card — violation checking wired into session flow
# ---------------------------------------------------------------------------


class TestRunCardViolationWiring:
    """AgentSession.run_card() must invoke _check_violations after strategy execution."""

    def test_run_card_calls_check_violations(self, session, fake_repo):
        """run_card() should call _check_violations after the strategy runs."""
        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.completed,
            files_written=[],
            runtime_ms=100,
        )

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch("silverquillm.agent_session._check_violations", return_value=[]) as mock_cv,
            patch("silverquillm.agent_session._REPO_ROOT", fake_repo),
        ):
            session.setup_workspace()
            result = session.run_card()

        mock_cv.assert_called_once()
        assert result.status == CardRunStatus.completed

    def test_run_card_returns_violation_status_on_contamination(self, session, fake_repo):
        """run_card() should return violation status when _check_violations finds issues."""
        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.completed,
            files_written=[],
            runtime_ms=100,
        )

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch("silverquillm.agent_session._check_violations", return_value=["docs/hack.py was created"]),
            patch("silverquillm.agent_session._REPO_ROOT", fake_repo),
        ):
            session.setup_workspace()
            result = session.run_card()

        # Violation should cause the result to be overridden
        assert result.status == CardRunStatus.no_output

    def test_run_card_takes_snapshot_before_strategy(self, session, fake_repo):
        """run_card() should snapshot protected paths before calling strategy."""
        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.completed,
            files_written=[],
            runtime_ms=50,
        )

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch("silverquillm.agent_session._snapshot_all_protected") as mock_snap,
            patch("silverquillm.agent_session._check_violations", return_value=[]),
            patch("silverquillm.agent_session._REPO_ROOT", fake_repo),
        ):
            mock_snap.return_value = {}
            session.setup_workspace()
            session.run_card()

        mock_snap.assert_called()
