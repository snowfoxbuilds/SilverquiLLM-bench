"""Smoke tests with mock adapter — full harness pipeline end-to-end.

Zero LLM calls.  Uses :class:`MockAdapter` to drive the **actual** harness
layers (``AgentSession``, workspace setup, violation checking, result
persistence, aggregation, CLI) end-to-end.

Required test cases (per TODO item 16):
1. Blind mode happy path  — via AgentSession.run_card()
2. Impl+test mode happy path  — via AgentSession.run_card()
3. Timeout handling  — via AgentSession.run_card()
4. No output  — via AgentSession.run_card()
5. Violation detection (Issue #15 regression) — via AgentSession.run_card()
6. Aggregation — run 3 mock cards through the pipeline → run_summary.json
7. Mode-dependent workspace — AgentSession.setup_workspace()
8. --dry-run CLI flag — via click.testing.CliRunner
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from silverquillm.adapters.mock import MockAdapter
from silverquillm.agent_session import AgentSession
from silverquillm.config import AgentConfig, BenchmarkConfig
from silverquillm.strategies import CardRunResult, CardRunStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_CARD_SPEC: dict[str, Any] = {
    "name": "Mock Lightning Bolt",
    "mana_cost": "{R}",
    "type_line": "Instant",
    "oracle_text": "Deal 3 damage to any target.",
    "collector_number": "999",
    "card_dir_name": "999",
    "complexity_tier": "trivial",
}

_IMPL_SOURCE = """\
# Mock card implementation
from engine.card import Instant

class MockLightningBolt(Instant):
    name = "Mock Lightning Bolt"
    mana_cost = "{R}"
"""

_TESTS_SOURCE = """\
import pytest
from card_impl import MockLightningBolt

def test_name():
    card = MockLightningBolt()
    assert card.name == "Mock Lightning Bolt"
"""


def _make_config(
    tmp_path: Path,
    *,
    mode: str = "blind",
    adapter: str = "mock",
    timeout: int = 10,
) -> BenchmarkConfig:
    """Create a minimal BenchmarkConfig pointing at *tmp_path*."""
    return BenchmarkConfig(
        name="smoke-test",
        set_code="TST",
        model_name="mock-model",
        model_provider="mock",
        mode=mode,
        agent=AgentConfig(adapter=adapter, timeout_per_card=timeout),
        output_dir=str(tmp_path / "results"),
    )


def _make_card_dir(tmp_path: Path, spec: dict[str, Any] | None = None) -> str:
    """Create a card directory with card_spec.json and return its path."""
    spec = spec or _MINIMAL_CARD_SPEC
    card_dir = tmp_path / "card_dir"
    card_dir.mkdir(parents=True, exist_ok=True)
    (card_dir / "card_spec.json").write_text(json.dumps(spec))
    return str(card_dir)


def _make_session(
    tmp_path: Path,
    *,
    mode: str = "blind",
    timeout: int = 10,
    spec: dict[str, Any] | None = None,
    behavior: str = "write",
    impl_source: str | None = None,
    tests_source: str | None = None,
) -> AgentSession:
    """Create an AgentSession wired to a MockAdapter with the given behavior.

    Monkey-patches ``_adapter`` to inject a pre-configured MockAdapter
    so we control adapter behavior precisely.
    """
    spec = spec or _MINIMAL_CARD_SPEC
    cfg = _make_config(tmp_path, mode=mode, timeout=timeout)
    card_dir = _make_card_dir(tmp_path, spec)

    run_dir = tmp_path / "run_output"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "cards").mkdir(exist_ok=True)

    # Create a run engine directory so AgentSession doesn't use the real one
    run_engine_dir = run_dir / "run_engine"
    repo_engine = Path(__file__).resolve().parent.parent / "engine"
    if repo_engine.exists():
        shutil.copytree(repo_engine, run_engine_dir)
    else:
        run_engine_dir.mkdir(parents=True, exist_ok=True)

    session = AgentSession(
        config=cfg,
        card_spec=spec,
        card_dir=card_dir,
        run_engine_dir=run_engine_dir,
        run_dir=run_dir,
    )

    # Inject the mock adapter with specific behavior
    mock_adapter = MockAdapter(
        cfg,
        behavior=behavior,
        impl_source=impl_source or _IMPL_SOURCE,
        tests_source=tests_source or _TESTS_SOURCE,
    )
    session._adapter = mock_adapter

    return session


# ---------------------------------------------------------------------------
# 1. Blind mode happy path
# ---------------------------------------------------------------------------


class TestBlindModeHappyPath:
    """MockAdapter writes card_impl.py → AgentSession.run_card() → completed."""

    def test_blind_session_completed(self, tmp_path: Path) -> None:
        """AgentSession.run_card() returns completed when MockAdapter writes card_impl.py."""
        session = _make_session(tmp_path, mode="blind", behavior="write")
        try:
            session.setup_workspace()
            result = session.run_card()
            assert result.status == CardRunStatus.completed
        finally:
            session.cleanup()

    def test_blind_impl_in_workspace(self, tmp_path: Path) -> None:
        """card_impl.py exists in workspace after blind mode run."""
        session = _make_session(tmp_path, mode="blind", behavior="write")
        try:
            ws = session.setup_workspace()
            session.run_card()
            assert (ws / "card_impl.py").exists()
        finally:
            session.cleanup()

    def test_blind_harvest_copies_to_results(self, tmp_path: Path) -> None:
        """harvest_results copies card_impl.py to the results directory."""
        session = _make_session(tmp_path, mode="blind", behavior="write")
        try:
            ws = session.setup_workspace()
            session.run_card()
            card_results_dir = tmp_path / "card_results"
            session.harvest_results(card_results_dir)
            assert (card_results_dir / "card_impl.py").exists()
        finally:
            session.cleanup()

    def test_blind_no_tests_written(self, tmp_path: Path) -> None:
        """Blind mode with behavior='write' should not create tests.py."""
        session = _make_session(tmp_path, mode="blind", behavior="write")
        try:
            ws = session.setup_workspace()
            session.run_card()
            assert not (ws / "tests.py").exists()
        finally:
            session.cleanup()


# ---------------------------------------------------------------------------
# 2. Impl+test mode happy path
# ---------------------------------------------------------------------------


class TestImplTestModeHappyPath:
    """MockAdapter writes card_impl.py + tests.py → AgentSession → completed."""

    def test_impl_test_session_completed(self, tmp_path: Path) -> None:
        """AgentSession.run_card() returns completed when both files are written."""
        session = _make_session(
            tmp_path, mode="impl_test", behavior="write_with_tests",
        )
        try:
            session.setup_workspace()
            result = session.run_card()
            assert result.status == CardRunStatus.completed
        finally:
            session.cleanup()

    def test_impl_test_both_files_exist(self, tmp_path: Path) -> None:
        """Both card_impl.py and tests.py exist in workspace after run."""
        session = _make_session(
            tmp_path, mode="impl_test", behavior="write_with_tests",
        )
        try:
            ws = session.setup_workspace()
            session.run_card()
            assert (ws / "card_impl.py").exists()
            assert (ws / "tests.py").exists()
        finally:
            session.cleanup()

    def test_impl_test_harvest_both_files(self, tmp_path: Path) -> None:
        """harvest_results copies both files to results directory."""
        session = _make_session(
            tmp_path, mode="impl_test", behavior="write_with_tests",
        )
        try:
            ws = session.setup_workspace()
            session.run_card()
            card_results_dir = tmp_path / "card_results"
            session.harvest_results(card_results_dir)
            assert (card_results_dir / "card_impl.py").exists()
            assert (card_results_dir / "tests.py").exists()
        finally:
            session.cleanup()


# ---------------------------------------------------------------------------
# 3. Timeout handling
# ---------------------------------------------------------------------------


class TestTimeoutHandling:
    """MockAdapter sleeps forever → timeout → status is timeout."""

    def test_timeout_status_via_session(self, tmp_path: Path) -> None:
        """AgentSession.run_card() returns timeout when adapter sleeps past deadline."""
        session = _make_session(tmp_path, mode="blind", behavior="timeout", timeout=2)
        try:
            session.setup_workspace()
            result = session.run_card()
            assert result.status == CardRunStatus.timeout
        finally:
            session.cleanup()

    def test_timeout_runtime_recorded(self, tmp_path: Path) -> None:
        """Runtime should be approximately the timeout duration."""
        session = _make_session(tmp_path, mode="blind", behavior="timeout", timeout=2)
        try:
            session.setup_workspace()
            result = session.run_card()
            # Runtime should be at least close to 2s
            assert result.runtime_ms >= 1000
        finally:
            session.cleanup()

    def test_timeout_engine_rolled_back(self, tmp_path: Path) -> None:
        """On timeout, the run engine directory should be rolled back to pre-run state."""
        session = _make_session(tmp_path, mode="blind", behavior="timeout", timeout=2)
        try:
            ws = session.setup_workspace()
            run_engine = session.run_engine_dir

            result = session.run_card()
            assert result.status == CardRunStatus.timeout

            # Engine snapshot should be cleaned up after restore
            if run_engine and run_engine.exists():
                snapshot = run_engine.with_suffix(".snapshot")
                assert not snapshot.exists(), "Snapshot should be cleaned up after restore"
        finally:
            session.cleanup()


# ---------------------------------------------------------------------------
# 4. No output
# ---------------------------------------------------------------------------


class TestNoOutput:
    """MockAdapter writes nothing → status is no_output via AgentSession."""

    def test_no_output_status_via_session(self, tmp_path: Path) -> None:
        """AgentSession.run_card() returns no_output when adapter writes nothing."""
        session = _make_session(tmp_path, mode="blind", behavior="no_output")
        try:
            session.setup_workspace()
            result = session.run_card()
            assert result.status == CardRunStatus.no_output
        finally:
            session.cleanup()

    def test_no_output_no_card_impl(self, tmp_path: Path) -> None:
        """card_impl.py should not exist in workspace after no_output run."""
        session = _make_session(tmp_path, mode="blind", behavior="no_output")
        try:
            ws = session.setup_workspace()
            session.run_card()
            assert not (ws / "card_impl.py").exists()
        finally:
            session.cleanup()

    def test_no_output_empty_harvest(self, tmp_path: Path) -> None:
        """harvest_results should find nothing to copy."""
        session = _make_session(tmp_path, mode="blind", behavior="no_output")
        try:
            session.setup_workspace()
            session.run_card()
            card_results_dir = tmp_path / "card_results"
            session.harvest_results(card_results_dir)
            if card_results_dir.exists():
                assert not (card_results_dir / "card_impl.py").exists()
        finally:
            session.cleanup()


# ---------------------------------------------------------------------------
# 5. Violation detection (Issue #15 regression)
# ---------------------------------------------------------------------------


class TestViolationDetection:
    """MockAdapter writes to protected path → violation recorded via AgentSession."""

    def test_violation_detected_by_session(self, tmp_path: Path) -> None:
        """AgentSession.run_card() detects violations and sets status accordingly."""
        session = _make_session(tmp_path, mode="blind", behavior="violation")
        violation_path = Path(__file__).resolve().parent.parent / "cards" / "_mock_violation.py"
        try:
            session.setup_workspace()
            result = session.run_card()
            # Violation should cause status to change to no_output
            # (per AgentSession._check_violations logic)
            assert result.violations, "Violations list should not be empty"
            assert result.status == CardRunStatus.no_output
        finally:
            session.cleanup()
            if violation_path.exists():
                violation_path.unlink()

    def test_violation_files_still_harvested(self, tmp_path: Path) -> None:
        """Files should still be harvestable despite violation (Issue #15)."""
        session = _make_session(tmp_path, mode="blind", behavior="violation")
        violation_path = Path(__file__).resolve().parent.parent / "cards" / "_mock_violation.py"
        try:
            ws = session.setup_workspace()
            result = session.run_card()
            # card_impl.py should still exist in workspace
            assert (ws / "card_impl.py").exists()
            # Harvest should copy the file
            card_results_dir = tmp_path / "card_results"
            session.harvest_results(card_results_dir)
            assert (card_results_dir / "card_impl.py").exists()
        finally:
            session.cleanup()
            if violation_path.exists():
                violation_path.unlink()

    def test_violation_recorded_in_result(self, tmp_path: Path) -> None:
        """Violation descriptions should be present in CardRunResult.violations."""
        session = _make_session(tmp_path, mode="blind", behavior="violation")
        violation_path = Path(__file__).resolve().parent.parent / "cards" / "_mock_violation.py"
        try:
            session.setup_workspace()
            result = session.run_card()
            assert len(result.violations) >= 1
            # At least one violation should mention the protected path
            violation_text = " ".join(result.violations)
            assert "_mock_violation" in violation_text or "cards" in violation_text
        finally:
            session.cleanup()
            if violation_path.exists():
                violation_path.unlink()


# ---------------------------------------------------------------------------
# 6. Aggregation — run 3 mock cards through the pipeline
# ---------------------------------------------------------------------------


class TestAggregation:
    """Run 3 mock cards through AgentSession → run_summary.json produced."""

    def test_run_summary_json_produced(self, tmp_path: Path) -> None:
        """Running 3 cards through the full pipeline produces run_summary.json."""
        from silverquillm.aggregator import aggregate_run, save_run_summary_v2
        from silverquillm.results import init_results_dir, save_card_result_v2
        from silverquillm.evaluator import EvalResultV2

        cfg = _make_config(tmp_path, mode="blind")
        run_dir = init_results_dir(cfg, run_name="agg-test", base_dir=tmp_path / "agg")

        # Run engine directory
        run_engine_dir = run_dir / "run_engine"
        repo_engine = Path(__file__).resolve().parent.parent / "engine"
        if repo_engine.exists():
            shutil.copytree(repo_engine, run_engine_dir)
        else:
            run_engine_dir.mkdir(parents=True, exist_ok=True)

        for i in range(3):
            spec = {
                **_MINIMAL_CARD_SPEC,
                "name": f"Mock Card {i}",
                "collector_number": str(100 + i),
                "card_dir_name": str(100 + i),
            }
            # Create a card dir with card_spec.json
            card_dir = tmp_path / f"card_{i}"
            card_dir.mkdir(parents=True, exist_ok=True)
            (card_dir / "card_spec.json").write_text(json.dumps(spec))

            session = AgentSession(
                config=cfg,
                card_spec=spec,
                card_dir=str(card_dir),
                run_engine_dir=run_engine_dir,
                run_dir=run_dir,
            )
            # Inject mock adapter
            mock_adapter = MockAdapter(
                cfg,
                behavior="write",
                impl_source=f"# Card {i}\nclass MockCard{i}:\n    pass\n",
            )
            session._adapter = mock_adapter

            try:
                session.setup_workspace()
                result = session.run_card()
                assert result.status == CardRunStatus.completed

                # Persist result using v2 schema
                card_results_dir = run_dir / "cards" / str(100 + i)
                session.harvest_results(card_results_dir)

                v2_result = EvalResultV2(
                    card_id=str(100 + i),
                    mode="blind",
                    model_name="mock-model",
                    adapter="mock",
                    status="completed",
                    complexity_tier="trivial",
                    implementation={
                        "tokens": 0,
                        "runtime_ms": result.runtime_ms,
                        "peak_context": 0,
                    },
                    errors=[],
                )
                save_card_result_v2(
                    run_dir, v2_result,
                    impl_source=f"# Card {i}",
                    tests_source="",
                )
            finally:
                session.cleanup()

        # Aggregate
        summary = aggregate_run(run_dir)
        out_path = save_run_summary_v2(run_dir, summary)

        assert out_path.exists(), "run_summary.json should be produced"
        data = json.loads(out_path.read_text())
        assert data["total_cards"] == 3
        assert data["cards_completed"] == 3

    def test_aggregate_mixed_statuses(self, tmp_path: Path) -> None:
        """Aggregation correctly counts mixed statuses (completed + no_output)."""
        from silverquillm.aggregator import aggregate_run, save_run_summary_v2
        from silverquillm.results import init_results_dir, save_card_result_v2
        from silverquillm.evaluator import EvalResultV2

        cfg = _make_config(tmp_path, mode="blind")
        run_dir = init_results_dir(cfg, run_name="mixed-test", base_dir=tmp_path / "mixed")

        run_engine_dir = run_dir / "run_engine"
        repo_engine = Path(__file__).resolve().parent.parent / "engine"
        if repo_engine.exists():
            shutil.copytree(repo_engine, run_engine_dir)
        else:
            run_engine_dir.mkdir(parents=True, exist_ok=True)

        behaviors = ["write", "write", "no_output"]
        for i, behavior in enumerate(behaviors):
            spec = {
                **_MINIMAL_CARD_SPEC,
                "name": f"Mixed Card {i}",
                "collector_number": str(200 + i),
                "card_dir_name": str(200 + i),
            }
            card_dir = tmp_path / f"mixed_card_{i}"
            card_dir.mkdir(parents=True, exist_ok=True)
            (card_dir / "card_spec.json").write_text(json.dumps(spec))

            session = AgentSession(
                config=cfg,
                card_spec=spec,
                card_dir=str(card_dir),
                run_engine_dir=run_engine_dir,
                run_dir=run_dir,
            )
            mock_adapter = MockAdapter(
                cfg,
                behavior=behavior,
                impl_source=f"# Card {i}\nclass Card{i}:\n    pass\n",
            )
            session._adapter = mock_adapter

            try:
                session.setup_workspace()
                result = session.run_card()

                card_results_dir = run_dir / "cards" / str(200 + i)
                session.harvest_results(card_results_dir)

                v2_result = EvalResultV2(
                    card_id=str(200 + i),
                    mode="blind",
                    model_name="mock-model",
                    adapter="mock",
                    status=result.status.value,
                    complexity_tier="trivial",
                    implementation={
                        "tokens": 0,
                        "runtime_ms": result.runtime_ms,
                        "peak_context": 0,
                    },
                    errors=[],
                )
                save_card_result_v2(
                    run_dir, v2_result,
                    impl_source=f"# Card {i}",
                    tests_source="",
                )
            finally:
                session.cleanup()

        summary = aggregate_run(run_dir)
        assert summary.total_cards == 3
        assert summary.cards_completed == 2


# ---------------------------------------------------------------------------
# 7. Mode-dependent workspace contents
# ---------------------------------------------------------------------------


class TestModeDependentWorkspace:
    """Blind mode workspace has no test_utils; impl_test mode has them."""

    def test_blind_workspace_no_test_utils(self, tmp_path: Path) -> None:
        """Blind mode workspace should NOT have test_utils.md or test_utils.py."""
        session = _make_session(tmp_path, mode="blind", behavior="write")
        try:
            ws = session.setup_workspace()
            assert not (ws / "test_utils.md").exists()
            assert not (ws / "test_utils.py").exists()
        finally:
            session.cleanup()

    def test_impl_test_workspace_has_test_utils(self, tmp_path: Path) -> None:
        """Impl_test mode workspace SHOULD include test_utils files (when available)."""
        session = _make_session(tmp_path, mode="impl_test", behavior="write_with_tests")
        try:
            ws = session.setup_workspace()
            # At least test_utils.py should be present if tests/test_utils.py exists in repo
            repo_root = Path(__file__).resolve().parent.parent
            test_utils_py = repo_root / "tests" / "test_utils.py"
            if test_utils_py.exists():
                assert (ws / "test_utils.py").exists()
            test_utils_md = repo_root / "docs" / "test_utils.md"
            if test_utils_md.exists():
                assert (ws / "test_utils.md").exists()
        finally:
            session.cleanup()

    def test_blind_vs_impl_test_workspace_difference(self, tmp_path: Path) -> None:
        """Blind and impl_test workspaces should differ in test_utils presence."""
        # Blind
        blind_dir = tmp_path / "blind_ws"
        blind_dir.mkdir()
        session_blind = _make_session(blind_dir, mode="blind", behavior="write")
        try:
            ws_blind = session_blind.setup_workspace()
            has_utils_blind = (ws_blind / "test_utils.py").exists()
        finally:
            session_blind.cleanup()

        # Impl test
        impl_dir = tmp_path / "impl_ws"
        impl_dir.mkdir()
        session_impl = _make_session(impl_dir, mode="impl_test", behavior="write_with_tests")
        try:
            ws_impl = session_impl.setup_workspace()
            has_utils_impl = (ws_impl / "test_utils.py").exists()
        finally:
            session_impl.cleanup()

        repo_root = Path(__file__).resolve().parent.parent
        if (repo_root / "tests" / "test_utils.py").exists():
            assert not has_utils_blind, "Blind mode should NOT have test_utils.py"
            assert has_utils_impl, "Impl_test mode SHOULD have test_utils.py"


# ---------------------------------------------------------------------------
# 8. CLI --dry-run flag
# ---------------------------------------------------------------------------


class TestDryRunCLI:
    """Verify --dry-run actually runs via the CLI and uses MockAdapter."""

    def test_dry_run_cli_invocation(self, tmp_path: Path) -> None:
        """Invoking the CLI with --dry-run should succeed without errors."""
        from click.testing import CliRunner
        from silverquillm.cli import main

        # Create a valid config file
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "name: dry-run-test\n"
            "set_code: sos\n"
            "model_name: mock-model\n"
            "model_provider: mock\n"
            "mode: blind\n"
            "agent:\n"
            "  adapter: mock\n"
            "  timeout_per_card: 5\n"
        )

        runner = CliRunner()
        result = runner.invoke(main, ["run", "--config", str(config_path), "--dry-run"])

        # Dry run should exit cleanly (exit code 0)
        assert result.exit_code == 0, f"CLI dry-run failed: {result.output}\n{result.exception}"

    def test_dry_run_mentions_mock_adapter(self, tmp_path: Path) -> None:
        """Dry-run output should mention MockAdapter."""
        from click.testing import CliRunner
        from silverquillm.cli import main

        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "name: dry-run-test\n"
            "set_code: sos\n"
            "model_name: mock-model\n"
            "model_provider: mock\n"
            "mode: blind\n"
            "agent:\n"
            "  adapter: mock\n"
            "  timeout_per_card: 5\n"
        )

        runner = CliRunner()
        result = runner.invoke(main, ["run", "--config", str(config_path), "--dry-run"])

        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "mock" in output_lower or "dry run" in output_lower

    def test_dry_run_lists_cards(self, tmp_path: Path) -> None:
        """Dry-run output should list selected cards."""
        from click.testing import CliRunner
        from silverquillm.cli import main

        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            "name: dry-run-test\n"
            "set_code: sos\n"
            "model_name: mock-model\n"
            "model_provider: mock\n"
            "mode: blind\n"
            "agent:\n"
            "  adapter: mock\n"
            "  timeout_per_card: 5\n"
        )

        runner = CliRunner()
        result = runner.invoke(main, ["run", "--config", str(config_path), "--dry-run"])

        assert result.exit_code == 0
        # Should mention number of cards selected
        assert "cards" in result.output.lower() or "Cards" in result.output


# ---------------------------------------------------------------------------
# MockAdapter unit tests (kept for coverage of adapter internals)
# ---------------------------------------------------------------------------


class TestMockAdapterUnit:
    """Direct unit tests for MockAdapter registration and basic ops."""

    def test_adapter_registered(self) -> None:
        """MockAdapter should be registered as 'mock' in the adapter registry."""
        from silverquillm.adapters.base import get_adapter
        cfg = _make_config(Path("/tmp/dummy"), mode="blind", adapter="mock")
        adapter = get_adapter(cfg)
        assert isinstance(adapter, MockAdapter)

    def test_setup_teardown_noop(self, tmp_path: Path) -> None:
        """setup() and teardown() should be no-ops."""
        cfg = _make_config(tmp_path, mode="blind")
        adapter = MockAdapter(cfg, behavior="write")
        adapter.setup()
        adapter.teardown()

    def test_kill_noop(self, tmp_path: Path) -> None:
        """kill() should be a no-op."""
        cfg = _make_config(tmp_path, mode="blind")
        adapter = MockAdapter(cfg, behavior="write")
        adapter.kill()
