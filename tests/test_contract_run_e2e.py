"""End-to-end Contract Run over the smoke benchmark — container-free.

Drives the full job-dir contract with a stub agent (a test double, no Docker):
stage the production job dir, run the stub — which reads the production-rendered
task, implements a known-good target, and writes its Output Proposal through the
*real* ``format-output`` CLI (never ``proposal.json`` by hand) — replay the
gate, validate with the production validator, apply the proposal as a driver
commit, run the three-dimension Audited Eval, and write a RunRecord.  Further
cases prove a missing proposal and a non-completing agent still harvest, grade,
and record.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from theozolith_worker import api

from silverquillm.contract import drive_contract_run
from silverquillm.jobdir import load_benchmark
from silverquillm.modes import get_mode
from silverquillm.proposal import PROPOSAL_APPLIED, PROPOSAL_MISSING
from silverquillm.results_repo import read_run_record

REPO = Path(__file__).resolve().parents[1]
HOB = REPO / "benchmarks/hob-medium/workspace/cards/fdn"


def _format_output(job_dir: Path, field: str, value: str) -> None:
    env = {**os.environ, "THEOZOLITH_JOB": str(job_dir)}
    proc = subprocess.run(
        ["format-output", field, value], env=env, capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, f"format-output {field} failed: {proc.stderr}"


def _make_stub_agent(*, write_proposal: bool, outcome: api.AgentOutcome | None = None):
    def agent(*, job_dir: Path) -> api.AgentOutcome:
        checkout = job_dir / "checkout"
        # The task rides input/prompt.md, rendered by production.
        task = (job_dir / "input" / "prompt.md").read_text()
        assert "Implementer in TheOzolith" in task and "129" in task
        shutil.copy2(
            HOB / "fdn_129" / "card_impl.py",
            checkout / "cards/fdn/fdn_129/card_impl.py",
        )
        if write_proposal:
            # Round-one implementer fields, via the real in-image CLI.
            _format_output(job_dir, "pr-title", "Smoke targets")
            _format_output(job_dir, "pr-description", "Implements the smoke pool.")
            _format_output(job_dir, "commit-message", "Implement Leyline Axe\n\nbody")
        return outcome or api.AgentOutcome(completed=True)

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

        # Proposal applied as a driver commit carrying the production trailer.
        assert result.proposal_status == PROPOSAL_APPLIED
        log = subprocess.run(
            ["git", "log", "-1", "--format=%B"],
            cwd=run_dir / "workspace_final", capture_output=True, text=True, check=True,
        ).stdout
        assert "Implement Leyline Axe" in log
        assert "Ozolith-Run: smoke-e2e-1" in log

        # The gate replayed the production sequence in order.
        assert result.gate.steps_run == ["test", "lint"]

        # Three-dimension results computed from benchmarks/smoke/data/tests/audited/.
        assert result.eval_result.sos_results["fdn_129"].tests_passed >= 8
        assert result.eval_result.fdn_results
        assert result.eval_result.engine_result.tests_total > 0

        # RunRecord persisted with benchmark: "smoke" and execution evidence.
        assert result.record_dir is not None
        record = read_run_record(result.record_dir)
        assert record.benchmark == "smoke" and record.mode == "basic"
        assert record.proposal_status == PROPOSAL_APPLIED
        assert record.run_metadata["gate"]["steps_run"] == ["test", "lint"]
        assert record.run_metadata["agent_outcome"]["completed"] is True
        assert any(p["kind"] == "run-artifacts" for p in record.artifact_pointers)

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
        # The checkout was still committed (fallback message) and evaluated.
        assert (run_dir / "workspace_final" / ".git").is_dir()
        assert result.eval_result.sos_results["fdn_129"].tests_passed >= 8
        assert read_run_record(result.record_dir).proposal_status == PROPOSAL_MISSING

    def test_non_completion_still_harvests_grades_and_records(self, tmp_path: Path) -> None:
        run_dir = tmp_path / "run"
        repo = tmp_path / "results"
        repo.mkdir()

        result = drive_contract_run(
            run_dir=run_dir,
            run_id="smoke-e2e-died",
            benchmark=load_benchmark("smoke"),
            mode=get_mode("basic"),
            budget_seconds=600,
            agent_runner=_make_stub_agent(
                write_proposal=True,
                outcome=api.AgentOutcome(session_died=True, exit_code=1),
            ),
            results_repo=repo,
            image="cc-e2e:latest",
            eval_timeout=120,
        )

        # A non-zero exit does not abort harvest/eval; the outcome is recorded.
        assert result.agent_outcome.session_died is True
        assert result.eval_result.sos_results["fdn_129"].tests_passed >= 8
        record = read_run_record(result.record_dir)
        assert record.run_metadata["agent_outcome"]["state"] == "session died (exit 1)"
