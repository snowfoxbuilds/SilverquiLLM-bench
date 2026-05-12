"""Tests for the production-like timeout-result path in engine snapshot/rollback.

When production strategies catch adapter timeouts internally, they return
CardRunResult(status=timeout) instead of raising subprocess.TimeoutExpired.
run_card() must detect this and restore the engine snapshot so corrupted
partial modifications cannot poison subsequent cards.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from silverquillm.agent_session import AgentSession
from silverquillm.config import AgentConfig, BenchmarkConfig
from silverquillm.strategies import CardRunResult, CardRunStatus


_SAMPLE_SPEC = {
    "name": "Grizzly Bears",
    "mana_cost": "{1}{G}",
    "type_line": "Creature — Bear",
    "oracle_text": "",
    "power": "2",
    "toughness": "2",
}


def _make_config(tmp_path: Path, **overrides) -> BenchmarkConfig:
    output_dir = tmp_path / "output"
    output_dir.mkdir(exist_ok=True)
    defaults = dict(
        name="test-bench",
        set_code="TST",
        model_name="test-model",
        model_provider="test",
        max_context=200_000,
        temperature=0.0,
        mode="blind",
        output_dir=str(output_dir),
        agent=AgentConfig(timeout_per_card=10, adapter="mock"),
    )
    defaults.update(overrides)
    return BenchmarkConfig(**defaults)


def _make_session(
    tmp_path: Path,
    run_engine_dir: Path | None = None,
    **config_overrides,
) -> AgentSession:
    config = _make_config(tmp_path, **config_overrides)
    card_dir = tmp_path / "card_data"
    card_dir.mkdir(exist_ok=True)
    (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))
    return AgentSession(
        config=config,
        card_spec=_SAMPLE_SPEC,
        card_dir=str(card_dir),
        run_engine_dir=run_engine_dir,
        run_dir=tmp_path / "output",
    )


class TestRunCardTimeoutResultRestoresEngine:
    """When strategy returns CardRunResult(status=timeout), engine must be restored."""

    @patch("silverquillm.agent_session._snapshot_all_protected", return_value={})
    @patch("silverquillm.agent_session._check_violations", return_value=[])
    def test_engine_restored_on_timeout_result(
        self, _mock_violations, _mock_protected, tmp_path: Path
    ) -> None:
        """Strategy returning timeout result must trigger engine rollback."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("original_content")
        (run_engine / "helper.py").write_text("helper_original")

        session = _make_session(tmp_path, run_engine_dir=run_engine)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        session._workspace = workspace

        def _timeout_result_side_effect(*args, **kwargs):
            # Simulate agent corrupting engine before adapter timeout is caught
            (run_engine / "card.py").write_text("corrupted_by_agent")
            (run_engine / "injected.py").write_text("bad new file")
            (run_engine / "helper.py").unlink()
            return CardRunResult(
                status=CardRunStatus.timeout,
                runtime_ms=10000,
            )

        with (
            patch("silverquillm.strategies.get_strategy") as mock_gs,
            patch("silverquillm.agent_session.get_adapter"),
        ):
            mock_strategy = MagicMock()
            mock_strategy.run_card.side_effect = _timeout_result_side_effect
            mock_gs.return_value = mock_strategy

            result = session.run_card()

        # Engine fully restored
        assert (run_engine / "card.py").read_text() == "original_content"
        assert (run_engine / "helper.py").read_text() == "helper_original"
        assert not (run_engine / "injected.py").exists()
        # Snapshot cleaned up after restore
        assert not run_engine.with_suffix(".snapshot").exists()
        # Result is timeout
        assert result.status == CardRunStatus.timeout

    @patch("silverquillm.agent_session._snapshot_all_protected", return_value={})
    @patch("silverquillm.agent_session._check_violations", return_value=[])
    def test_corrupted_engine_not_committed_after_timeout_result(
        self, _mock_violations, _mock_protected, tmp_path: Path
    ) -> None:
        """After timeout result, run_engine_dir must contain only pre-card state."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "game.py").write_text("class Game: pass")

        session = _make_session(tmp_path, run_engine_dir=run_engine)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        session._workspace = workspace

        def _corrupt_and_timeout(*args, **kwargs):
            (run_engine / "game.py").write_text("CORRUPTED")
            (run_engine / "malicious.py").write_text("import os; os.system('bad')")
            return CardRunResult(
                status=CardRunStatus.timeout,
                runtime_ms=10000,
            )

        with (
            patch("silverquillm.strategies.get_strategy") as mock_gs,
            patch("silverquillm.agent_session.get_adapter"),
        ):
            mock_strategy = MagicMock()
            mock_strategy.run_card.side_effect = _corrupt_and_timeout
            mock_gs.return_value = mock_strategy

            session.run_card()

        # Verify the engine dir is clean — a subsequent card or CLI commit
        # would see only original state, not corrupted files
        assert (run_engine / "game.py").read_text() == "class Game: pass"
        assert not (run_engine / "malicious.py").exists()

    @patch("silverquillm.agent_session._snapshot_all_protected", return_value={})
    @patch("silverquillm.agent_session._check_violations", return_value=[])
    def test_success_result_preserves_engine_changes(
        self, _mock_violations, _mock_protected, tmp_path: Path
    ) -> None:
        """Successful result must NOT restore engine (changes are intentional)."""
        run_engine = tmp_path / "run_engine"
        run_engine.mkdir()
        (run_engine / "card.py").write_text("before")

        session = _make_session(tmp_path, run_engine_dir=run_engine)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        session._workspace = workspace

        def _success_with_changes(*args, **kwargs):
            (run_engine / "card.py").write_text("improved")
            return CardRunResult(
                status=CardRunStatus.completed,
                files_written=["card_impl.py"],
                runtime_ms=200,
            )

        with (
            patch("silverquillm.strategies.get_strategy") as mock_gs,
            patch("silverquillm.agent_session.get_adapter"),
        ):
            mock_strategy = MagicMock()
            mock_strategy.run_card.side_effect = _success_with_changes
            mock_gs.return_value = mock_strategy

            result = session.run_card()

        assert result.status == CardRunStatus.completed
        assert (run_engine / "card.py").read_text() == "improved"
