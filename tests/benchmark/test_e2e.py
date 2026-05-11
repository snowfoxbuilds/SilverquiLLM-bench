"""Full pipeline integration test with Eager Glyphmage and Ajani's Response.

Validates the end-to-end benchmark flow: workspace setup, blind implementation,
test-informed refinement, result saving, evaluation, scoring, and leaderboard
generation.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from silverquillm.agent_session import AgentSession, BlindResult
from silverquillm.config import BenchmarkConfig
from silverquillm.evaluator import run_self_eval_flat
from silverquillm.results import init_results_dir, save_card_result, save_run_summary
from silverquillm.scorer import Leaderboard, compute_scores, generate_leaderboard
from silverquillm.results import save_aggregates
from tests.benchmark.test_helpers import (
    create_test_config,
    mock_opencode_blind,
    mock_opencode_test_informed,
)

# Path to card specs in the repository
_CARDS_DIR = Path(__file__).resolve().parent.parent.parent / "benchmarks" / "sos" / "cards"


def _load_card_spec(collector_number: str) -> dict:
    """Load a card_spec.json from benchmarks/sos/cards/{collector_number}/."""
    spec_path = _CARDS_DIR / collector_number / "card_spec.json"
    return json.loads(spec_path.read_text())


@pytest.mark.integration
class TestBenchmarkEndToEnd:
    """End-to-end integration tests for the benchmark pipeline."""

    def test_full_pipeline_two_cards(self, tmp_path: Path) -> None:
        """Run the full pipeline for Eager Glyphmage and Ajani's Response."""
        # 1. Load card specs
        card_spec_11 = _load_card_spec("11")
        card_spec_6 = _load_card_spec("6")

        assert card_spec_11["collector_number"] == "11"
        assert card_spec_6["collector_number"] == "6"

        # 2. Create BenchmarkConfig
        config = create_test_config(tmp_path)

        # Track artifacts per card for later result saving
        card_artifacts: dict[str, dict] = {}

        for card_id, card_spec in [("11", card_spec_11), ("6", card_spec_6)]:
            card_dir = str(_CARDS_DIR / card_id)

            # 3a. Create AgentSession
            session = AgentSession(
                config=config,
                card_spec=card_spec,
                card_dir=card_dir,
            )

            # 3b. Monkey-patch _run_agent
            blind_mock = mock_opencode_blind(card_spec)
            test_mock = mock_opencode_test_informed(card_spec)
            call_count = {"n": 0}

            def _patched_run_agent(prompt: str, workspace: Path, _bm=blind_mock, _tm=test_mock, _cc=call_count) -> str:
                _cc["n"] += 1
                if _cc["n"] == 1:
                    return _bm(prompt, workspace)
                return _tm(prompt, workspace)

            session._run_agent = _patched_run_agent  # type: ignore[assignment]

            # Also patch _run_pytest to avoid needing 'python' binary
            def _mock_pytest(workspace: Path, tests_path: Path) -> subprocess.CompletedProcess:
                return subprocess.CompletedProcess(
                    args=["pytest"], returncode=0, stdout="3 passed\n", stderr=""
                )

            session._run_pytest = _mock_pytest  # type: ignore[assignment]

            # 3c. Setup workspace
            workspace = session.setup_workspace()

            # 3d. Assert workspace contents
            assert (workspace / "card_spec.json").exists()
            assert (workspace / "engine_api.md").exists()
            assert (workspace / "base_classes.py").exists()
            assert (workspace / "template.py").exists()
            assert (workspace / "rules_overview.md").exists()
            assert (workspace / "foundations").is_dir()

            # 3e. Run blind implementation
            blind_result = session.run_blind_implementation(workspace)
            assert blind_result.status == "ok"
            assert blind_result.impl_path is not None
            assert blind_result.impl_path.exists()

            # 3f. Run test-informed
            test_informed_result = session.run_test_informed(workspace, blind_result.impl_path)
            assert test_informed_result.impl_path is not None
            assert test_informed_result.tests_path is not None

            # 3g. Read sources before cleanup
            impl_source = blind_result.impl_path.read_text()
            tested_source = test_informed_result.impl_path.read_text()
            tests_source = test_informed_result.tests_path.read_text()

            # 3h. Cleanup
            session.cleanup()
            assert not workspace.exists()

            # Store artifacts for result saving
            card_artifacts[card_id] = {
                "blind_result": {
                    "impl_source": impl_source,
                    "agent": config.agent.adapter,
                    "model": config.model_name,
                    "complexity_tier": "simple",
                    "status": blind_result.status,
                    "tokens": blind_result.tokens,
                    "runtime_seconds": blind_result.runtime_seconds,
                    "peak_context": blind_result.peak_context,
                },
                "test_result": {
                    "impl_source": tested_source,
                    "tests_source": tests_source,
                    "agent": config.agent.adapter,
                    "model": config.model_name,
                    "complexity_tier": "simple",
                    "status": test_informed_result.status,
                    "tokens": test_informed_result.tokens,
                    "runtime_seconds": test_informed_result.runtime_seconds,
                    "peak_context": test_informed_result.peak_context,
                    "iterations": test_informed_result.iterations,
                },
            }

        # 4. Save results
        run_dir = init_results_dir(config, run_name="test-run")
        for card_id, artifacts in card_artifacts.items():
            save_card_result(
                run_dir,
                card_id=card_id,
                blind_result=artifacts["blind_result"],
                test_result=artifacts["test_result"],
            )

        # 5. Assert directory structure
        assert (run_dir / "cards" / "11" / "result.json").exists()
        assert (run_dir / "cards" / "6" / "result.json").exists()
        assert (run_dir / "cards" / "11" / "blind_impl.py").exists()
        assert (run_dir / "cards" / "11" / "tested_impl.py").exists()
        assert (run_dir / "cards" / "6" / "blind_impl.py").exists()
        assert (run_dir / "cards" / "6" / "tested_impl.py").exists()

        # Assert both agent (tool) and model fields are present in result records
        for card_id in ["11", "6"]:
            result = json.loads((run_dir / "cards" / card_id / "result.json").read_text())
            assert result["agent"] == config.agent.adapter
            assert result["model"] == config.model_name

        # 6. Run self-eval
        eval_results = []
        for card_id in ["11", "6"]:
            eval_result = run_self_eval_flat(
                run_dir / "cards" / card_id,
                agent_name=config.model_name,
            )
            assert eval_result.card_id == card_id
            assert eval_result.blind_total > 0
            assert eval_result.tested_total > 0
            assert eval_result.errors == []
            eval_results.append(eval_result)

        # 7. Save run summary
        all_results = []
        for card_id in ["11", "6"]:
            result_json = run_dir / "cards" / card_id / "result.json"
            all_results.append(json.loads(result_json.read_text()))

        summary_path = save_run_summary(run_dir, all_results)
        assert summary_path.exists()
        summary = json.loads(summary_path.read_text())
        assert summary["card_count"] == 2

        # 8. Compute scores
        tier_data = {"11": "simple", "6": "simple"}
        # Use real eval results from step 6
        from dataclasses import asdict

        eval_results_for_scorer = [asdict(er) for er in eval_results]

        scorer_dir = tmp_path / "scorer_input"
        scorer_dir.mkdir()
        (scorer_dir / "results.json").write_text(json.dumps(eval_results_for_scorer))

        leaderboard = compute_scores(scorer_dir, tier_data)
        assert isinstance(leaderboard, Leaderboard)

        # 9. Generate leaderboard markdown
        lb_markdown = generate_leaderboard(leaderboard)
        assert len(lb_markdown) > 0
        assert "Category 1" in lb_markdown

        # 10. Save aggregates
        results_dir = tmp_path / "aggregates"
        results_dir.mkdir()
        save_aggregates(results_dir, [run_dir], leaderboard)
        assert (results_dir / "leaderboard.md").exists()

    def test_workspace_contamination_detected(self, tmp_path: Path) -> None:
        """Verify contamination detection when agent writes to a protected dir (docs/)."""
        card_spec = _load_card_spec("11")
        config = create_test_config(tmp_path)
        card_dir = str(_CARDS_DIR / "11")

        fake_docs = tmp_path / "docs"
        fake_docs.mkdir()

        with patch("silverquillm.agent_session._REPO_ROOT", tmp_path):
            session = AgentSession(
                config=config,
                card_spec=card_spec,
                card_dir=card_dir,
            )

            workspace = session.setup_workspace()

            def _contaminating_opencode(prompt: str, ws: Path) -> str:
                (ws / "blind_impl.py").write_text("class Foo: pass\n")
                (fake_docs / "_test_contamination_marker.py").write_text("# contamination\n")
                return "done"

            session._run_agent = _contaminating_opencode  # type: ignore[assignment]

            result = session.run_blind_implementation(workspace)
            assert result.status == "violation"
            session.cleanup()
