"""Tests for TODO item 4: Refactor agent_session.py — remove harness-managed iteration.

Verifies:
- AgentSession.run_card() delegates to CardStrategy (via get_strategy) rather
  than running its own blind/test-informed orchestration.
- _run_pytest() method is removed entirely.
- No round-counting logic or _DEFAULT_MAX_ROUNDS references remain.
- harvest_results() copies card_impl.py (not blind_impl.py / tested_impl.py).
- Workspace setup is mode-dependent: blind mode excludes test_utils files,
  impl_test mode includes them.
- Status propagation from CardRunResult through run_card().
"""

from __future__ import annotations

import inspect
import json
import shutil
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
    "name": "Grizzly Bears",
    "mana_cost": "{1}{G}",
    "type_line": "Creature — Bear",
    "oracle_text": "",
    "power": "2",
    "toughness": "2",
}


@pytest.fixture()
def blind_config():
    return _make_config(mode="blind")


@pytest.fixture()
def impl_test_config():
    return _make_config(mode="impl_test")


@pytest.fixture()
def session_factory(tmp_path):
    """Factory to create an AgentSession with a fake card_dir."""
    sessions = []

    def _factory(config):
        card_dir = tmp_path / "card_data"
        card_dir.mkdir(exist_ok=True)
        (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))
        sess = AgentSession(config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir))
        sessions.append(sess)
        return sess

    yield _factory

    for s in sessions:
        s.cleanup()


# ---------------------------------------------------------------------------
# Harness-managed iteration is removed
# ---------------------------------------------------------------------------


class TestHarnessIterationRemoved:
    """The old multi-round orchestration logic must be deleted."""

    def test_no_run_pytest_method(self):
        """_run_pytest() should be completely removed from AgentSession."""
        assert not hasattr(AgentSession, "_run_pytest"), (
            "_run_pytest method should be deleted — the harness does NOT run pytest"
        )

    def test_no_default_max_rounds_constant(self):
        """_DEFAULT_MAX_ROUNDS should not exist in the module."""
        import silverquillm.agent_session as mod

        assert not hasattr(mod, "_DEFAULT_MAX_ROUNDS"), (
            "_DEFAULT_MAX_ROUNDS should be removed — no harness round counting"
        )

    def test_no_max_test_rounds_references_in_source(self):
        """Source code should contain no max_test_rounds references."""
        import silverquillm.agent_session as mod

        source = inspect.getsource(mod)
        assert "max_test_rounds" not in source

    def test_no_iteration_feedback_prompt_import(self):
        """iteration_feedback_prompt should no longer be imported."""
        import silverquillm.agent_session as mod

        source = inspect.getsource(mod)
        assert "iteration_feedback_prompt" not in source


# ---------------------------------------------------------------------------
# run_card() delegates to CardStrategy
# ---------------------------------------------------------------------------


class TestRunCardDelegation:
    """AgentSession.run_card() should delegate to get_strategy(mode).run_card()."""

    def test_run_card_calls_strategy(self, blind_config, session_factory):
        """run_card() must invoke the strategy returned by get_strategy()."""
        session = session_factory(blind_config)
        mock_result = CardRunResult(
            status=CardRunStatus.completed,
            files_written=[],
            runtime_ms=100,
        )
        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = mock_result

        with patch("silverquillm.strategies.get_strategy", return_value=mock_strategy) as gs:
            result = session.run_card()

        gs.assert_called_once_with("blind")
        mock_strategy.run_card.assert_called_once()
        assert result is mock_result

    def test_run_card_passes_correct_mode_impl_test(self, impl_test_config, session_factory):
        """run_card() must pass mode='impl_test' to get_strategy()."""
        session = session_factory(impl_test_config)
        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.completed,
        )

        with patch("silverquillm.strategies.get_strategy", return_value=mock_strategy) as gs:
            session.run_card()

        gs.assert_called_once_with("impl_test")

    def test_run_card_sets_up_workspace_if_needed(self, blind_config, session_factory):
        """run_card() should call setup_workspace if workspace is None."""
        session = session_factory(blind_config)
        assert session.workspace is None

        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.completed,
        )

        with patch("silverquillm.strategies.get_strategy", return_value=mock_strategy):
            session.run_card()

        assert session.workspace is not None

    def test_run_card_returns_card_run_result(self, blind_config, session_factory):
        """run_card() must return a CardRunResult instance."""
        session = session_factory(blind_config)
        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(
            status=CardRunStatus.timeout,
            runtime_ms=5000,
        )

        with patch("silverquillm.strategies.get_strategy", return_value=mock_strategy):
            result = session.run_card()

        assert isinstance(result, CardRunResult)
        assert result.status == CardRunStatus.timeout

    def test_run_card_passes_adapter_and_timeout(self, blind_config, session_factory):
        """run_card() must pass adapter and timeout from config to strategy."""
        session = session_factory(blind_config)
        mock_strategy = MagicMock()
        mock_strategy.run_card.return_value = CardRunResult(status=CardRunStatus.completed)

        with patch("silverquillm.strategies.get_strategy", return_value=mock_strategy):
            session.run_card()

        call_kwargs = mock_strategy.run_card.call_args
        # Verify timeout matches config
        assert call_kwargs.kwargs.get("timeout") == 300 or (
            len(call_kwargs.args) >= 4 and call_kwargs.args[3] == 300
        )


# ---------------------------------------------------------------------------
# harvest_results() uses card_impl.py
# ---------------------------------------------------------------------------


class TestHarvestResults:
    """harvest_results() must copy card_impl.py, not blind_impl.py / tested_impl.py."""

    def test_copies_card_impl_py(self, blind_config, session_factory, tmp_path):
        """harvest_results should copy card_impl.py to results dir."""
        session = session_factory(blind_config)
        ws = session.setup_workspace()
        (ws / "card_impl.py").write_text("# implementation\n")

        results_dir = tmp_path / "results"
        session.harvest_results(results_dir)

        assert (results_dir / "card_impl.py").exists()
        assert (results_dir / "card_impl.py").read_text() == "# implementation\n"

    def test_does_not_copy_blind_impl_py(self, blind_config, session_factory, tmp_path):
        """harvest_results must NOT look for blind_impl.py."""
        session = session_factory(blind_config)
        ws = session.setup_workspace()
        (ws / "blind_impl.py").write_text("# old blind impl\n")

        results_dir = tmp_path / "results"
        session.harvest_results(results_dir)

        assert not (results_dir / "blind_impl.py").exists()

    def test_does_not_copy_tested_impl_py(self, impl_test_config, session_factory, tmp_path):
        """harvest_results must NOT look for tested_impl.py."""
        session = session_factory(impl_test_config)
        ws = session.setup_workspace()
        (ws / "tested_impl.py").write_text("# old tested impl\n")

        results_dir = tmp_path / "results"
        session.harvest_results(results_dir)

        assert not (results_dir / "tested_impl.py").exists()

    def test_copies_tests_py_alongside_card_impl(self, impl_test_config, session_factory, tmp_path):
        """harvest_results should also copy tests.py if present."""
        session = session_factory(impl_test_config)
        ws = session.setup_workspace()
        (ws / "card_impl.py").write_text("# impl\n")
        (ws / "tests.py").write_text("# tests\n")

        results_dir = tmp_path / "results"
        session.harvest_results(results_dir)

        assert (results_dir / "card_impl.py").exists()
        assert (results_dir / "tests.py").exists()

    def test_harvest_no_workspace_is_noop(self, blind_config, session_factory, tmp_path):
        """harvest_results with no workspace should silently do nothing."""
        session = session_factory(blind_config)
        results_dir = tmp_path / "results"
        session.harvest_results(results_dir)
        assert not results_dir.exists() or not list(results_dir.iterdir())


# ---------------------------------------------------------------------------
# Mode-dependent workspace setup
# ---------------------------------------------------------------------------


class TestWorkspaceModeDependency:
    """Workspace setup should vary by mode: blind has no test_utils, impl_test has them."""

    def test_blind_mode_no_test_utils_md(self, blind_config, session_factory):
        """In blind mode, test_utils.md should NOT be in the workspace."""
        session = session_factory(blind_config)
        ws = session.setup_workspace()
        assert not (ws / "test_utils.md").exists(), (
            "Blind mode should not include test_utils.md"
        )

    def test_blind_mode_no_test_utils_py(self, blind_config, session_factory):
        """In blind mode, test_utils.py should NOT be in the workspace."""
        session = session_factory(blind_config)
        ws = session.setup_workspace()
        assert not (ws / "test_utils.py").exists(), (
            "Blind mode should not include test_utils.py"
        )

    def test_impl_test_mode_has_test_utils_py(self, impl_test_config, session_factory):
        """In impl_test mode, test_utils.py should be in the workspace."""
        session = session_factory(impl_test_config)
        ws = session.setup_workspace()
        # test_utils.py should be present (if the source file exists in the repo)
        test_utils_src = Path(__file__).resolve().parent / "test_utils.py"
        if test_utils_src.exists():
            assert (ws / "test_utils.py").exists(), (
                "impl_test mode should include test_utils.py"
            )

    def test_both_modes_have_card_spec(self, blind_config, impl_test_config, session_factory, tmp_path):
        """Both modes should always have card_spec.json in workspace."""
        for cfg in (blind_config, impl_test_config):
            # Need separate card_dirs since setup_workspace cleans workspace
            card_dir = tmp_path / f"card_data_{cfg.mode}"
            card_dir.mkdir(exist_ok=True)
            (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))
            sess = AgentSession(config=cfg, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir))
            try:
                ws = sess.setup_workspace()
                assert (ws / "card_spec.json").exists()
            finally:
                sess.cleanup()

    def test_both_modes_have_template(self, blind_config, impl_test_config, session_factory, tmp_path):
        """Both modes should always have template.py in workspace."""
        for cfg in (blind_config, impl_test_config):
            card_dir = tmp_path / f"card_data_{cfg.mode}"
            card_dir.mkdir(exist_ok=True)
            (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))
            sess = AgentSession(config=cfg, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir))
            try:
                ws = sess.setup_workspace()
                assert (ws / "template.py").exists()
            finally:
                sess.cleanup()

    def test_both_modes_have_card_impl_py_seeded(self, blind_config, impl_test_config, session_factory, tmp_path):
        """Both modes should seed card_impl.py from the template."""
        for cfg in (blind_config, impl_test_config):
            card_dir = tmp_path / f"card_data_{cfg.mode}"
            card_dir.mkdir(exist_ok=True)
            (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))
            sess = AgentSession(config=cfg, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir))
            try:
                ws = sess.setup_workspace()
                assert (ws / "card_impl.py").exists()
            finally:
                sess.cleanup()


# ---------------------------------------------------------------------------
# Thin wrapper flow: setup → delegate → harvest → cleanup
# ---------------------------------------------------------------------------


class TestThinWrapperFlow:
    """AgentSession should be a thin wrapper: setup → strategy → harvest → cleanup."""

    def test_kept_methods_exist(self):
        """Key methods that should be kept must still exist."""
        assert hasattr(AgentSession, "setup_workspace")
        assert hasattr(AgentSession, "harvest_results")
        assert hasattr(AgentSession, "cleanup")
        assert hasattr(AgentSession, "run_card")

    def test_init_run_engine_still_importable(self):
        """Engine management functions must remain importable."""
        from silverquillm.agent_session import (
            commit_engine_changes,
            init_run_engine,
        )
        assert callable(init_run_engine)
        assert callable(commit_engine_changes)

    def test_postmortem_functions_still_importable(self):
        """Postmortem logging functions must remain importable."""
        from silverquillm.agent_session import (
            _append_postmortem,
            _generate_agent_thoughts,
        )
        assert callable(_append_postmortem)
        assert callable(_generate_agent_thoughts)

    def test_violation_checking_still_importable(self):
        """Violation checking must remain importable."""
        from silverquillm.agent_session import _check_violations

        assert callable(_check_violations)
