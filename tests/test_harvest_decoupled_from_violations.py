"""Tests for TODO item 5: Decouple harvest_results() from violation status.

Requirements verified:
1. harvest_results() must run unconditionally — always copy card_impl.py and
   tests.py from the workspace regardless of violation status.
2. Violations annotate CardRunResult (via a ``violations`` field) but don't
   prevent file capture.
3. run_card() must NOT destroy the workspace or skip file writing when
   violations are detected.
4. Non-violation harvesting remains unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from silverquillm.agent_session import AgentSession
from silverquillm.config import AgentConfig, BenchmarkConfig
from silverquillm.strategies import CardRunResult, CardRunStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(mode: str = "blind", **overrides) -> BenchmarkConfig:
    defaults = dict(
        name="test-bench",
        set_code="SOS",
        model_name="test-model",
        model_provider="test-provider",
        max_context=200_000,
        temperature=0.0,
        mode=mode,
        agent=AgentConfig(timeout_per_card=300),
    )
    defaults.update(overrides)
    return BenchmarkConfig(**defaults)


_SAMPLE_SPEC = {
    "name": "Ral Zarek",
    "mana_cost": "{2}{U}{R}",
    "type_line": "Legendary Planeswalker — Ral",
    "oracle_text": (
        "+1: Tap target permanent, then untap another target permanent.\n"
        "-2: Ral Zarek deals 3 damage to any target.\n"
        "-7: Flip five coins. Take an extra turn for each heads."
    ),
    "loyalty": "4",
}


@pytest.fixture()
def fake_repo(tmp_path):
    """Minimal fake repo root with protected directories."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for dirname in ("engine", "cards", "tests", "benchmark", "benchmarks", "docs"):
        d = repo / dirname
        d.mkdir()
        (d / "existing.py").write_text(f"# {dirname}\n")
    return repo


@pytest.fixture()
def session(tmp_path, fake_repo):
    """An AgentSession wired to a temp card_dir."""
    card_dir = tmp_path / "card_data"
    card_dir.mkdir()
    (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))
    config = _make_config()
    sess = AgentSession(config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir))
    yield sess
    sess.cleanup()


def _make_strategy_mock(status=CardRunStatus.completed, runtime_ms=100):
    """Return a mock strategy whose run_card returns the given result."""
    mock = MagicMock()
    mock.run_card.return_value = CardRunResult(
        status=status, files_written=[], runtime_ms=runtime_ms,
    )
    return mock


# ---------------------------------------------------------------------------
# CardRunResult.violations field contract
# ---------------------------------------------------------------------------


class TestCardRunResultViolationsField:
    """CardRunResult must carry a violations list that defaults to empty."""

    def test_violations_field_present(self):
        r = CardRunResult(status=CardRunStatus.completed)
        assert hasattr(r, "violations"), "CardRunResult must expose a violations attribute"

    def test_violations_defaults_empty(self):
        r = CardRunResult(status=CardRunStatus.completed)
        assert r.violations == [], "violations must default to an empty list"

    def test_violations_accepts_list(self):
        r = CardRunResult(
            status=CardRunStatus.no_output,
            violations=["docs/hack.py was created", "engine/core.py was modified"],
        )
        assert len(r.violations) == 2


# ---------------------------------------------------------------------------
# harvest_results() runs unconditionally (core requirement)
# ---------------------------------------------------------------------------


class TestHarvestRunsUnconditionally:
    """harvest_results() must copy card_impl.py and tests.py regardless of
    whether a violation was detected during run_card()."""

    def test_card_impl_harvested_after_violation(self, session, fake_repo, tmp_path):
        """Ral Zarek scenario: violation detected, card_impl.py still harvested."""
        results_dir = tmp_path / "results"
        mock_strategy = _make_strategy_mock()

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch(
                "silverquillm.agent_session._check_violations",
                return_value=["docs/hack.py was created"],
            ),
            patch("silverquillm.agent_session._REPO_ROOT", fake_repo),
        ):
            session.setup_workspace()
            (session.workspace / "card_impl.py").write_text("class RalZarek: pass\n")
            result = session.run_card()

        # Violation recorded
        assert result.violations, "violations must be non-empty when _check_violations returns issues"

        # Workspace is still alive for harvesting
        assert session.workspace is not None
        assert (session.workspace / "card_impl.py").exists(), (
            "card_impl.py must still exist in workspace after violation"
        )

        # Harvest succeeds
        session.harvest_results(results_dir)
        assert (results_dir / "card_impl.py").exists(), (
            "card_impl.py MUST be harvested even when violations were detected"
        )
        assert (results_dir / "card_impl.py").read_text() == "class RalZarek: pass\n"

    def test_tests_py_harvested_after_violation(self, session, fake_repo, tmp_path):
        """tests.py must also be captured despite violation."""
        results_dir = tmp_path / "results"
        mock_strategy = _make_strategy_mock()

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch(
                "silverquillm.agent_session._check_violations",
                return_value=["engine/modified.py content changed"],
            ),
            patch("silverquillm.agent_session._REPO_ROOT", fake_repo),
        ):
            session.setup_workspace()
            (session.workspace / "card_impl.py").write_text("# impl\n")
            (session.workspace / "tests.py").write_text("def test_ral(): assert True\n")
            result = session.run_card()

        assert result.violations

        session.harvest_results(results_dir)
        assert (results_dir / "tests.py").exists(), (
            "tests.py MUST be harvested even when violations were detected"
        )
        assert (results_dir / "tests.py").read_text() == "def test_ral(): assert True\n"

    def test_both_files_harvested_after_violation(self, session, fake_repo, tmp_path):
        """Both card_impl.py and tests.py must be present in results dir."""
        results_dir = tmp_path / "results"
        mock_strategy = _make_strategy_mock()

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch(
                "silverquillm.agent_session._check_violations",
                return_value=["cards/evil.py was created"],
            ),
            patch("silverquillm.agent_session._REPO_ROOT", fake_repo),
        ):
            session.setup_workspace()
            (session.workspace / "card_impl.py").write_text("class RalZarek: pass\n")
            (session.workspace / "tests.py").write_text("def test_ral(): pass\n")
            session.run_card()

        session.harvest_results(results_dir)
        assert (results_dir / "card_impl.py").exists()
        assert (results_dir / "tests.py").exists()

    def test_workspace_not_destroyed_by_violation(self, session, fake_repo):
        """run_card() must NOT destroy the workspace when violations are found."""
        mock_strategy = _make_strategy_mock()

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch(
                "silverquillm.agent_session._check_violations",
                return_value=["docs/hack.py was created"],
            ),
            patch("silverquillm.agent_session._REPO_ROOT", fake_repo),
        ):
            session.setup_workspace()
            (session.workspace / "card_impl.py").write_text("# impl\n")
            session.run_card()

        # Workspace must still exist for subsequent harvest_results() call
        assert session.workspace is not None
        assert session.workspace.exists()
        assert (session.workspace / "card_impl.py").exists()


# ---------------------------------------------------------------------------
# Violations annotate result but don't block harvest
# ---------------------------------------------------------------------------


class TestViolationAnnotation:
    """Violations must be recorded in CardRunResult.violations without
    preventing file capture."""

    def test_violation_populates_result_violations_field(self, session, fake_repo):
        """run_card() must populate result.violations when _check_violations returns issues."""
        mock_strategy = _make_strategy_mock()
        violations_list = ["docs/hack.py was created", "tests/existing.py was modified"]

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch("silverquillm.agent_session._check_violations", return_value=violations_list),
            patch("silverquillm.agent_session._REPO_ROOT", fake_repo),
        ):
            session.setup_workspace()
            (session.workspace / "card_impl.py").write_text("# impl\n")
            result = session.run_card()

        assert result.violations == violations_list
        assert len(result.violations) == 2

    def test_clean_run_has_empty_violations(self, session, fake_repo, tmp_path):
        """When no violations are detected, violations list must be empty."""
        results_dir = tmp_path / "results"
        mock_strategy = _make_strategy_mock()

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch("silverquillm.agent_session._check_violations", return_value=[]),
            patch("silverquillm.agent_session._REPO_ROOT", fake_repo),
        ):
            session.setup_workspace()
            (session.workspace / "card_impl.py").write_text("# clean impl\n")
            result = session.run_card()

        assert result.violations == []
        assert result.status == CardRunStatus.completed

        # Harvest still works normally
        session.harvest_results(results_dir)
        assert (results_dir / "card_impl.py").exists()

    def test_violation_status_is_no_output(self, session, fake_repo):
        """When violations are detected, status should be no_output."""
        mock_strategy = _make_strategy_mock()

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch(
                "silverquillm.agent_session._check_violations",
                return_value=["docs/hack.py was created"],
            ),
            patch("silverquillm.agent_session._REPO_ROOT", fake_repo),
        ):
            session.setup_workspace()
            (session.workspace / "card_impl.py").write_text("# impl\n")
            result = session.run_card()

        assert result.status == CardRunStatus.no_output
        # But violations are still recorded
        assert len(result.violations) > 0


# ---------------------------------------------------------------------------
# Non-violation harvesting unchanged
# ---------------------------------------------------------------------------


class TestNonViolationHarvestUnchanged:
    """Normal (no-violation) harvest behavior must remain the same."""

    def test_harvest_copies_card_impl_no_violation(self, session, fake_repo, tmp_path):
        results_dir = tmp_path / "results"
        mock_strategy = _make_strategy_mock()

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch("silverquillm.agent_session._check_violations", return_value=[]),
            patch("silverquillm.agent_session._REPO_ROOT", fake_repo),
        ):
            session.setup_workspace()
            (session.workspace / "card_impl.py").write_text("# impl\n")
            session.run_card()

        session.harvest_results(results_dir)
        assert (results_dir / "card_impl.py").exists()
        assert (results_dir / "card_impl.py").read_text() == "# impl\n"

    def test_harvest_copies_tests_py_no_violation(self, session, fake_repo, tmp_path):
        results_dir = tmp_path / "results"
        mock_strategy = _make_strategy_mock()

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch("silverquillm.agent_session._check_violations", return_value=[]),
            patch("silverquillm.agent_session._REPO_ROOT", fake_repo),
        ):
            session.setup_workspace()
            (session.workspace / "card_impl.py").write_text("# impl\n")
            (session.workspace / "tests.py").write_text("# tests\n")
            session.run_card()

        session.harvest_results(results_dir)
        assert (results_dir / "tests.py").exists()

    def test_harvest_noop_when_no_workspace(self, tmp_path):
        """harvest_results with no workspace should silently do nothing."""
        card_dir = tmp_path / "card_data"
        card_dir.mkdir()
        (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))
        config = _make_config()
        sess = AgentSession(config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir))
        try:
            results_dir = tmp_path / "results"
            sess.harvest_results(results_dir)
            assert not results_dir.exists() or not list(results_dir.iterdir())
        finally:
            sess.cleanup()

    def test_harvest_skips_missing_files_gracefully(self, session, fake_repo, tmp_path):
        """If card_impl.py doesn't exist in workspace, harvest should not error."""
        results_dir = tmp_path / "results"
        mock_strategy = _make_strategy_mock(status=CardRunStatus.no_output)

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch("silverquillm.agent_session._check_violations", return_value=[]),
            patch("silverquillm.agent_session._REPO_ROOT", fake_repo),
        ):
            session.setup_workspace()
            # Don't write card_impl.py — agent produced nothing
            session.run_card()

        # Should not raise
        session.harvest_results(results_dir)
