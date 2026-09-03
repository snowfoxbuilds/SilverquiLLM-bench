"""Tests for the Contract Run RunRecord writer and candidate-segment mapping."""

from __future__ import annotations

from pathlib import Path

from theozolith_worker import api

from silverquillm.contract import (
    FAILURE_EVALUATION,
    PHASE_DONE,
    ContractRunResult,
    RunFailure,
)
from silverquillm.contract_record import (
    EVIDENCE_KIND,
    RUN_ARTIFACTS_KIND,
    image_candidate_segment,
    write_contract_run_record,
)
from silverquillm.contract_version import CONTRACT_SCHEMA_VERSION, InstalledWorker
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


def _result(tmp_path: Path, run_id: str, mode: str, **overrides) -> ContractRunResult:
    fields = {
        "run_dir": tmp_path / "artifacts" / run_id,
        "run_id": run_id,
        "benchmark_id": "smoke",
        "mode_name": mode,
        "image": "cc-test:latest",
        "budget_seconds": 600,
        "phase": PHASE_DONE,
        "worker": InstalledWorker(
            version="0.3.0", revision="a" * 40, source="git+x", tree_digest="b" * 64
        ),
        "job_dir": tmp_path / "artifacts" / run_id / "job",
        "agent_outcome": api.AgentOutcome(completed=True, exit_code=0),
        "harness_status": {"phase": "done", "error": "", "agent": {"completed": True}},
        "transcript": {"path": "output/transcript.txt", "bytes": 12, "lines": 3},
        "gate": api.GateResult(steps_run=["test", "lint"]),
        "proposal_status": "applied",
        "started_at": "2026-09-02T10:00:00+00:00",
    }
    fields.update(overrides)
    return ContractRunResult(**fields)


class TestWriteContractRunRecord:
    def _write(self, repo: Path, result: ContractRunResult, eval_result: FullEvalResult | None) -> Path:
        return write_contract_run_record(
            results_repo=repo,
            run_id=result.run_id,
            image=result.image,
            benchmark=load_benchmark("smoke"),
            mode=get_mode(result.mode_name),
            budget_seconds=result.budget_seconds,
            proposal_status=result.proposal_status,
            eval_result=eval_result,
            evidence=result.evidence(),
        )

    def test_record_round_trips(self, tmp_path: Path) -> None:
        rec_dir = self._write(tmp_path, _result(tmp_path, "run-1", "basic"), FullEvalResult())
        record = read_run_record(rec_dir)
        assert record.benchmark == "smoke"
        assert record.mode == "basic"
        assert record.proposal_status == "applied"
        assert record.leaderboard_valid is False
        assert set(record.scores) == {"card_correctness", "fdn_regression", "engine_regression"}
        assert all(score["evaluated"] is True for score in record.scores.values())

    def test_records_the_execution_evidence(self, tmp_path: Path) -> None:
        result = _result(
            tmp_path, "run-2", "basic",
            agent_outcome=api.AgentOutcome(session_died=True, exit_code=1),
            harness_status={"phase": "done", "error": "", "agent": {"session_died": True}},
            gate=api.GateResult(
                steps_run=["test", "lint"],
                findings=[api.Finding(step="test", severity="error", summary="boom")],
            ),
        )
        rec_dir = self._write(tmp_path, result, FullEvalResult())
        record = read_run_record(rec_dir)
        meta = record.run_metadata
        assert meta["contract_schema_version"] == CONTRACT_SCHEMA_VERSION
        assert meta["worker"] == {
            "version": "0.3.0", "revision": "a" * 40, "source": "git+x", "tree_digest": "b" * 64,
        }
        assert meta["adapter"] == "claude"
        assert meta["run_date"] == "2026-09-02T10:00:00+00:00"
        assert meta["agent_outcome"]["session_died"] is True
        assert meta["agent_outcome"]["exit_code"] == 1
        assert meta["harness_status"]["agent"]["session_died"] is True
        assert meta["transcript"]["lines"] == 3
        assert meta["gate"]["steps_run"] == ["test", "lint"]
        assert meta["gate"]["clean"] is False
        assert meta["phase"] == PHASE_DONE and meta["failure"] is None
        pointers = {p["kind"]: p["location"] for p in record.artifact_pointers}
        assert pointers[RUN_ARTIFACTS_KIND] == str(result.run_dir)
        assert pointers[EVIDENCE_KIND] == str(result.run_dir / "contract_run.json")

    def test_unevaluated_run_is_attempted_with_zeroed_marked_scores(self, tmp_path: Path) -> None:
        failure = RunFailure(FAILURE_EVALUATION, "evaluation", "grader exploded", "Traceback ...")
        result = _result(tmp_path, "run-3", "basic", phase="evaluation", failures=[failure])
        record = read_run_record(self._write(tmp_path, result, None))
        assert record.run_metadata["evaluated"] is False
        assert record.run_metadata["failure"] == failure.to_dict()
        assert record.run_metadata["failures"] == [failure.to_dict()]
        assert record.run_metadata["phase"] == "evaluation"
        for score in record.scores.values():
            assert score == {
                "pass_rate": 0.0, "tests_passed": 0, "tests_total": 0, "cards": 0, "evaluated": False,
            }

    def test_mode_is_not_part_of_candidate_identity(self, tmp_path: Path) -> None:
        """AC: no mode string is folded into the candidate identity — two runs
        of the same image under different modes share a candidate directory."""
        basic_dir = self._write(tmp_path, _result(tmp_path, "run-basic", "basic"), FullEvalResult())
        planned_dir = self._write(tmp_path, _result(tmp_path, "run-planned", "planned"), FullEvalResult())
        assert basic_dir.parent == planned_dir.parent
        basic_rec = read_run_record(basic_dir)
        assert basic_dir.parent.name == candidate_hash(basic_rec.candidate)
