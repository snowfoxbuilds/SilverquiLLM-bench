"""End-to-end Contract Run over the smoke benchmark — container-free.

Drives the full job-dir contract with a stub agent (a test double, no Docker):
stage the smoke workspace + job dir, run the stub (which reads the task, copies
a known-good target impl, and writes a valid Output Proposal), apply the
proposal as a driver commit, run the three-dimension Audited Eval, and write a
RunRecord into a temp results repo. A second run proves a missing proposal does
not abort harvest or evaluation.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from silverquillm.contract import drive_contract_run
from silverquillm.jobdir import load_benchmark
from silverquillm.modes import get_mode
from silverquillm.proposal import PROPOSAL_APPLIED, PROPOSAL_MISSING
from silverquillm.results_repo import read_run_record

REPO = Path(__file__).resolve().parents[1]
HOB = REPO / "benchmarks/hob-medium/workspace/cards/fdn"


def _implement_fdn_129(workspace: Path) -> None:
    shutil.copy2(
        HOB / "fdn_129" / "card_impl.py",
        workspace / "cards/fdn/fdn_129/card_impl.py",
    )


def _make_stub_agent(*, write_proposal: bool):
    def agent(*, workspace: Path, output: Path, job_dir: Path) -> None:
        # The agent's assignment rides input/prompt.md.
        task = (job_dir / "input" / "prompt.md").read_text()
        assert "Implement the" in task and "fdn" in task
        _implement_fdn_129(workspace)
        if write_proposal:
            doc = {
                "schema_version": 1,
                "mode": "run",
                "fields": {
                    "commit-message": "Implement Leyline Axe",
                    "decisions": [{"what": "Implemented fdn_129", "why": "target card"}],
                    "pr-title": "Smoke targets",
                    "pr-description": "Implements the smoke target pool.",
                },
            }
            (job_dir / "output" / "proposal.json").write_text(json.dumps(doc))

    return agent


class TestContractRunE2E:
    def test_full_pipeline_writes_record_and_scores(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        repo = tmp_path / "results"
        repo.mkdir()

        result = drive_contract_run(
            run_dir=run_dir,
            run_id="smoke-e2e-1",
            benchmark=load_benchmark("smoke"),
            mode=get_mode("basic"),
            budget_seconds=600,
            agent_runner=_make_stub_agent(write_proposal=True),
            results_repo=repo,
            image="cc-e2e:latest",
            eval_timeout=120,
        )

        # Proposal applied as a driver commit carrying the provenance trailer.
        assert result.proposal_status == PROPOSAL_APPLIED
        log = subprocess.run(
            ["git", "log", "-1", "--format=%B"],
            cwd=run_dir / "workspace_final", capture_output=True, text=True, check=True,
        ).stdout
        assert "Implement Leyline Axe" in log
        assert "Silverquillm-Run: smoke-e2e-1 / smoke / basic" in log

        # Three-dimension results computed from benchmarks/smoke/data/tests/audited/.
        assert result.eval_result.sos_results["fdn_129"].tests_passed >= 8
        assert result.eval_result.fdn_results
        assert result.eval_result.engine_result.tests_total > 0

        # RunRecord persisted with benchmark: "smoke".
        assert result.record_dir is not None
        record = read_run_record(result.record_dir)
        assert record.benchmark == "smoke"
        assert record.mode == "basic"
        assert record.proposal_status == PROPOSAL_APPLIED
        assert set(record.scores) == {"card_correctness", "fdn_regression", "engine_regression"}

    def test_missing_proposal_still_harvests_and_evaluates(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        repo = tmp_path / "results"
        repo.mkdir()

        result = drive_contract_run(
            run_dir=run_dir,
            run_id="smoke-e2e-noproposal",
            benchmark=load_benchmark("smoke"),
            mode=get_mode("planned"),
            budget_seconds=600,
            agent_runner=_make_stub_agent(write_proposal=False),
            results_repo=repo,
            image="cc-e2e:latest",
            eval_timeout=120,
        )

        assert result.proposal_status == PROPOSAL_MISSING
        # The workspace was still committed (fallback message) and evaluated.
        assert (run_dir / "workspace_final" / ".git").is_dir()
        assert result.eval_result.sos_results["fdn_129"].tests_passed >= 8
        record = read_run_record(result.record_dir)
        assert record.proposal_status == PROPOSAL_MISSING
