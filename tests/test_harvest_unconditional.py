"""Tests for TODO item 5: Decouple harvest_results() from violation status.

Verifies:
- harvest_results() runs unconditionally even when violations are detected.
- Violations annotate CardRunResult.violations but do NOT prevent file capture.
- card_impl.py and tests.py are always copied to results dir regardless of
  violation status.
- CardRunResult has a violations field to carry violation details.
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
        set_code="FDN",
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
    "oracle_text": "+1: Tap target permanent, then untap another target permanent.\n-2: Ral Zarek deals 3 damage to any target.\n-7: Flip five coins. Take an extra turn after this one for each coin that comes up heads.",
    "loyalty": "4",
}


@pytest.fixture()
def fake_repo(tmp_path):
    """Create a fake repo root with protected directories."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for dirname in ("engine", "cards", "tests", "benchmark", "benchmarks", "docs"):
        d = repo / dirname
        d.mkdir()
        (d / "existing.py").write_text(f"# {dirname}\n")
    return repo


@pytest.fixture()
def session(tmp_path, fake_repo):
    """Create a session with a fake card_dir."""
    card_dir = tmp_path / "card_data"
    card_dir.mkdir()
    (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))

    config = _make_config()
    sess = AgentSession(config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir))
    yield sess
    sess.cleanup()


# ---------------------------------------------------------------------------
# CardRunResult carries violations
# ---------------------------------------------------------------------------


class TestCardRunResultViolations:
    """CardRunResult must have a violations field for annotation."""

    def test_violations_field_exists(self):
        """CardRunResult must have a violations field."""
        result = CardRunResult(status=CardRunStatus.completed)
        assert hasattr(result, "violations")

    def test_violations_defaults_to_empty_list(self):
        """violations should default to an empty list."""
        result = CardRunResult(status=CardRunStatus.completed)
        assert result.violations == []

    def test_violations_can_be_set(self):
        """violations can be populated with violation descriptions."""
        result = CardRunResult(
            status=CardRunStatus.no_output,
            violations=["docs/hack.py was created"],
        )
        assert result.violations == ["docs/hack.py was created"]


# ---------------------------------------------------------------------------
# harvest_results() runs unconditionally
# ---------------------------------------------------------------------------


class TestHarvestUnconditional:
    """harvest_results() must run regardless of violation status."""

    def test_harvest_called_even_with_violations(self, session, fake_repo, tmp_path):
        """When a violation is detected, card_impl.py must still be harvested."""
        results_dir = tmp_path / "results"

        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.completed,
            files_written=[],
            runtime_ms=100,
        )

        def _side_effect(**kwargs):
            # Simulate the agent writing card_impl.py AND contaminating docs
            ws = session.workspace
            (ws / "card_impl.py").write_text("class RalZarek: pass\n")
            return mock_strategy.run_card.return_value

        mock_strategy.run_card.side_effect = _side_effect

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch(
                "silverquillm.agent_session._check_violations",
                return_value=["docs/hack.py was created"],
            ),
            patch("silverquillm.agent_session._REPO_ROOT", fake_repo),
        ):
            session.setup_workspace()
            # Write card_impl.py in workspace to simulate agent output
            (session.workspace / "card_impl.py").write_text("class RalZarek: pass\n")
            result = session.run_card()

        # Violation should be recorded in result
        assert result.violations == ["docs/hack.py was created"]
        # Status should reflect the violation
        assert result.status == CardRunStatus.no_output

        # Now harvest and verify files are captured
        session.harvest_results(results_dir)
        assert (results_dir / "card_impl.py").exists()
        assert (results_dir / "card_impl.py").read_text() == "class RalZarek: pass\n"

    def test_violations_annotate_result_not_block_harvest(self, session, fake_repo, tmp_path):
        """Violations must annotate the result but harvest must still succeed."""
        results_dir = tmp_path / "results"

        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.completed,
            files_written=[],
            runtime_ms=200,
        )

        violations_list = ["tests/existing.py was modified", "docs/new.py was created"]

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch("silverquillm.agent_session._check_violations", return_value=violations_list),
            patch("silverquillm.agent_session._REPO_ROOT", fake_repo),
        ):
            session.setup_workspace()
            ws = session.workspace
            (ws / "card_impl.py").write_text("# Ral Zarek impl\n")
            (ws / "tests.py").write_text("# Ral Zarek tests\n")
            result = session.run_card()

        # Violations recorded
        assert len(result.violations) == 2
        assert "tests/existing.py was modified" in result.violations

        # Harvest unconditionally
        session.harvest_results(results_dir)
        assert (results_dir / "card_impl.py").exists()
        assert (results_dir / "tests.py").exists()

    def test_no_violations_result_clean(self, session, fake_repo, tmp_path):
        """When no violations, result should have empty violations list."""
        results_dir = tmp_path / "results"

        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.completed,
            files_written=[],
            runtime_ms=50,
        )

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

        session.harvest_results(results_dir)
        assert (results_dir / "card_impl.py").exists()

    def test_harvest_with_both_files_after_violation(self, session, fake_repo, tmp_path):
        """Both card_impl.py and tests.py must be harvested even after violation."""
        results_dir = tmp_path / "results"

        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.completed,
            files_written=[],
            runtime_ms=100,
        )

        with (
            patch("silverquillm.strategies.get_strategy", return_value=mock_strategy),
            patch(
                "silverquillm.agent_session._check_violations",
                return_value=["engine/hack.py created"],
            ),
            patch("silverquillm.agent_session._REPO_ROOT", fake_repo),
        ):
            session.setup_workspace()
            ws = session.workspace
            (ws / "card_impl.py").write_text("class RalZarek: pass\n")
            (ws / "tests.py").write_text("def test_ral(): pass\n")
            result = session.run_card()

        assert result.violations
        assert result.status == CardRunStatus.no_output

        session.harvest_results(results_dir)
        assert (results_dir / "card_impl.py").exists()
        assert (results_dir / "tests.py").exists()
        assert (results_dir / "card_impl.py").read_text() == "class RalZarek: pass\n"
        assert (results_dir / "tests.py").read_text() == "def test_ral(): pass\n"
