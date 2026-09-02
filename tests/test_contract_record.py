"""Tests for the Contract Run RunRecord writer and candidate-segment mapping."""

from __future__ import annotations

from pathlib import Path

from theozolith_worker import api

from silverquillm.contract_record import (
    image_candidate_segment,
    write_contract_run_record,
)
from silverquillm.evaluator import FullEvalResult
from silverquillm.jobdir import load_benchmark
from silverquillm.modes import get_mode
from silverquillm.results_repo import candidate_hash, read_run_record


class TestImageCandidateSegment:
    def test_strips_registry_tag_and_prefix(self) -> None:
        assert image_candidate_segment("ghcr.io/u/silverquillm-foo:latest") == "foo"

    def test_sanitizes_unsafe_characters(self) -> None:
        seg = image_candidate_segment("weird name!@#")
        assert "/" not in seg and " " not in seg and seg

    def test_none_is_handled(self) -> None:
        assert image_candidate_segment(None) == "unknown-image"


class TestWriteContractRunRecord:
    def _write(
        self,
        repo: Path,
        run_id: str,
        mode_name: str,
        *,
        outcome: api.AgentOutcome | None = None,
        gate: api.GateResult | None = None,
    ) -> Path:
        return write_contract_run_record(
            results_repo=repo,
            run_id=run_id,
            image="cc-test:latest",
            benchmark=load_benchmark("smoke"),
            mode=get_mode(mode_name),
            budget_seconds=600,
            proposal_status="applied",
            eval_result=FullEvalResult(),
            agent_outcome=outcome or api.AgentOutcome(completed=True),
            gate=gate or api.GateResult(steps_run=["test", "lint"]),
            run_dir=repo / "artifacts" / run_id,
        )

    def test_record_round_trips(self, tmp_path: Path) -> None:
        rec_dir = self._write(tmp_path, "run-1", "basic")
        record = read_run_record(rec_dir)
        assert record.benchmark == "smoke"
        assert record.mode == "basic"
        assert record.proposal_status == "applied"
        assert record.leaderboard_valid is False
        assert set(record.scores) == {"card_correctness", "fdn_regression", "engine_regression"}

    def test_records_execution_outcome_and_evidence(self, tmp_path: Path) -> None:
        outcome = api.AgentOutcome(session_died=True, exit_code=1)
        gate = api.GateResult(
            steps_run=["test", "lint"],
            findings=[api.Finding(step="test", severity="error", summary="boom")],
        )
        rec_dir = self._write(tmp_path, "run-2", "basic", outcome=outcome, gate=gate)
        meta = read_run_record(rec_dir).run_metadata
        assert meta["contract_schema_version"] == api.SCHEMA_VERSION
        assert meta["adapter"] == "claude"
        assert meta["product_version"] and meta["run_date"]
        assert meta["agent_outcome"]["session_died"] is True
        assert meta["agent_outcome"]["exit_code"] == 1
        assert meta["gate"]["steps_run"] == ["test", "lint"]
        assert meta["gate"]["clean"] is False
        # An artifact pointer locates the on-disk run dir (workspace/job/logs).
        pointers = read_run_record(rec_dir).artifact_pointers
        assert any(p["kind"] == "run-artifacts" for p in pointers)

    def test_mode_is_not_part_of_candidate_identity(self, tmp_path: Path) -> None:
        """AC: no mode string is folded into the candidate identity — two runs
        of the same image under different modes share a candidate directory."""
        basic_dir = self._write(tmp_path, "run-basic", "basic")
        planned_dir = self._write(tmp_path, "run-planned", "planned")
        assert basic_dir.parent == planned_dir.parent
        basic_rec = read_run_record(basic_dir)
        assert basic_dir.parent.name == candidate_hash(basic_rec.candidate)
