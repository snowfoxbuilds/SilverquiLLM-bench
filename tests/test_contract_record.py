"""Tests for the Contract Run RunRecord writer.

The record is written under the ``ozolith-v1`` identity the bench recomputed
from a Candidate Bundle (``verified: true`` — the only way such an identity
exists); adapter/product versions, the export timestamp and the built image
ride as run metadata only, and ``leaderboard_valid`` comes from its one owner.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from theozolith_worker import api

from silverquillm.candidate import BuiltImage, load_candidate_bundle
from silverquillm.contract import (
    FAILURE_EVALUATION,
    PHASE_DONE,
    ContractRunResult,
    RunFailure,
)
from silverquillm.contract_record import (
    CANDIDATE_BUNDLE_KIND,
    EVIDENCE_KIND,
    RUN_ARTIFACTS_KIND,
    write_contract_run_record,
)
from silverquillm.contract_version import CONTRACT_SCHEMA_VERSION, InstalledWorker
from silverquillm.evaluator import CardResult, FullEvalResult
from silverquillm.jobdir import BenchmarkRef, load_benchmark
from silverquillm.modes import get_mode
from silverquillm.results_repo import OZOLITH_SCHEME, candidate_hash, read_run_record
from tests.candidate_fixtures import export_bundle, fake_image_builder


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    root = tmp_path_factory.mktemp("bundle")
    path, _ = export_bundle(root)
    return load_candidate_bundle(path)


def _result(tmp_path: Path, run_id: str, mode: str, bundle, **overrides) -> ContractRunResult:
    fields = {
        "run_dir": tmp_path / "artifacts" / run_id,
        "run_id": run_id,
        "benchmark_id": "smoke",
        "mode_name": mode,
        "candidate_path": bundle.path,
        "budget_seconds": 600,
        "phase": PHASE_DONE,
        "worker": InstalledWorker(
            version="0.3.0", revision="a" * 40, source="git+x", tree_digest="b" * 64
        ),
        "bundle": bundle,
        "image": fake_image_builder(bundle),
        "bound_slots": ["ANTHROPIC_API_KEY"],
        "job_dir": tmp_path / "artifacts" / run_id / "job",
        "agent_outcome": api.AgentOutcome(completed=True, exit_code=0),
        "harness_status": {"phase": "done", "error": "", "agent": {"completed": True}},
        "transcript": {"path": "output/transcript.txt", "bytes": 12, "lines": 3},
        "gate": api.GateResult(steps_run=["test", "lint"]),
        "proposal_status": "applied",
        "started_at": "2026-09-03T10:00:00+00:00",
    }
    fields.update(overrides)
    return ContractRunResult(**fields)


def _write(repo: Path, result: ContractRunResult, eval_result, benchmark=None) -> Path:
    return write_contract_run_record(
        results_repo=repo,
        run_id=result.run_id,
        candidate=result.bundle.identity,
        benchmark=benchmark or load_benchmark("smoke"),
        mode=get_mode(result.mode_name),
        budget_seconds=result.budget_seconds,
        proposal_status=result.proposal_status,
        eval_result=eval_result,
        evidence=result.evidence(),
    )


class TestWriteContractRunRecord:
    def test_record_round_trips_under_the_verified_identity(self, tmp_path: Path, bundle) -> None:
        rec_dir = _write(tmp_path, _result(tmp_path, "run-1", "basic", bundle), FullEvalResult())
        record = read_run_record(rec_dir)
        assert record.benchmark == "smoke"
        assert record.mode == "basic"
        assert record.proposal_status == "applied"
        assert record.candidate == bundle.identity
        assert record.candidate.scheme == OZOLITH_SCHEME and record.candidate.verified is True
        assert rec_dir.parent.name == candidate_hash(bundle.identity) == bundle.candidate_hash
        assert record.leaderboard_valid is False  # smoke is never leaderboard-eligible
        assert set(record.scores) == {"card_correctness", "fdn_regression", "engine_regression"}
        assert all(score["evaluated"] is True for score in record.scores.values())

    def test_records_the_execution_and_candidate_evidence(self, tmp_path: Path, bundle) -> None:
        result = _result(
            tmp_path, "run-2", "basic", bundle,
            agent_outcome=api.AgentOutcome(session_died=True, exit_code=1),
            harness_status={"phase": "done", "error": "", "agent": {"session_died": True}},
            gate=api.GateResult(
                steps_run=["test", "lint"],
                findings=[api.Finding(step="test", severity="error", summary="boom")],
            ),
        )
        record = read_run_record(_write(tmp_path, result, FullEvalResult()))
        meta = record.run_metadata
        assert meta["contract_schema_version"] == CONTRACT_SCHEMA_VERSION
        assert meta["contract_bundle_format_version"] == 2
        assert meta["contract_identity_spec_version"] == 2
        assert meta["worker"] == {
            "version": "0.3.0", "revision": "a" * 40, "source": "git+x", "tree_digest": "b" * 64,
        }
        # Candidate metadata: adapter/product version/export time are metadata
        # only — never identity-bearing — and no secret value appears.
        assert meta["adapter"] == "claude"
        assert meta["worker_type"] == "fixture-claude"
        assert meta["model"] == "claude-sonnet-5"
        assert meta["product_version"] == "0.3.0"
        assert meta["exported_at"] == "2026-09-03T00:00:00Z"
        assert meta["image"] == result.image.to_dict()
        assert meta["secret_slots"] == {"bound": ["ANTHROPIC_API_KEY"], "unbound": []}
        assert meta["run_date"] == "2026-09-03T10:00:00+00:00"
        assert meta["agent_outcome"]["session_died"] is True
        assert meta["harness_status"]["agent"]["session_died"] is True
        assert meta["transcript"]["lines"] == 3
        assert meta["gate"]["steps_run"] == ["test", "lint"]
        assert meta["gate"]["clean"] is False
        assert meta["phase"] == PHASE_DONE and meta["failure"] is None
        pointers = {p["kind"]: p["location"] for p in record.artifact_pointers}
        assert pointers[RUN_ARTIFACTS_KIND] == str(result.run_dir)
        assert pointers[EVIDENCE_KIND] == str(result.run_dir / "contract_run.json")
        assert CANDIDATE_BUNDLE_KIND not in pointers  # nothing was vendored in this evidence

    def test_vendored_copy_is_pointed_at_from_the_record(self, tmp_path: Path, bundle) -> None:
        from silverquillm.candidate import VendoredCandidate

        vendored = VendoredCandidate(path=tmp_path / "results" / bundle.candidate_hash / "candidate", written=True)
        result = _result(tmp_path, "run-vendored", "basic", bundle, vendored=vendored)
        record = read_run_record(_write(tmp_path, result, FullEvalResult()))
        pointers = {p["kind"]: p["location"] for p in record.artifact_pointers}
        assert pointers[CANDIDATE_BUNDLE_KIND] == f"results/{bundle.candidate_hash}/candidate/"

    def test_unevaluated_run_is_attempted_with_zeroed_marked_scores(self, tmp_path: Path, bundle) -> None:
        failure = RunFailure(FAILURE_EVALUATION, "evaluation", "grader exploded", "Traceback ...")
        result = _result(tmp_path, "run-3", "basic", bundle, phase="evaluation", failures=[failure])
        record = read_run_record(_write(tmp_path, result, None))
        assert record.run_metadata["evaluated"] is False
        assert record.run_metadata["failure"] == failure.to_dict()
        assert record.run_metadata["failures"] == [failure.to_dict()]
        assert record.run_metadata["phase"] == "evaluation"
        assert record.leaderboard_valid is False
        for score in record.scores.values():
            assert score == {
                "pass_rate": 0.0, "tests_passed": 0, "tests_total": 0, "cards": 0, "evaluated": False,
            }

    def test_mode_is_not_part_of_candidate_identity(self, tmp_path: Path, bundle) -> None:
        """AC: no mode string is folded into the candidate identity — two runs
        of the same candidate under different modes share a candidate directory."""
        basic_dir = _write(tmp_path, _result(tmp_path, "run-basic", "basic", bundle), FullEvalResult())
        planned_dir = _write(tmp_path, _result(tmp_path, "run-planned", "planned", bundle), FullEvalResult())
        assert basic_dir.parent == planned_dir.parent
        basic_rec = read_run_record(basic_dir)
        assert basic_dir.parent.name == candidate_hash(basic_rec.candidate)

    def test_leaderboard_valid_comes_from_the_one_owner(self, tmp_path: Path, bundle) -> None:
        """An eligible benchmark whose whole card set was scored is valid; a
        partial scored set is not — the rule is derive_leaderboard_valid's."""
        eligible = BenchmarkRef(
            id="smoke",
            root=load_benchmark("smoke").root,
            config={"id": "smoke", "cards": ["129", "205"], "leaderboard": {"eligible": True}},
        )
        full = FullEvalResult(
            sos_results={
                "fdn_129": CardResult("129", tests_passed=1, tests_total=1),
                "fdn_205": CardResult("205", tests_passed=0, tests_total=1),
            }
        )
        record = read_run_record(
            _write(tmp_path, _result(tmp_path, "run-full", "basic", bundle), full, eligible)
        )
        assert record.leaderboard_valid is True
        partial = FullEvalResult(sos_results={"fdn_129": CardResult("129", tests_passed=1, tests_total=1)})
        record = read_run_record(
            _write(tmp_path, _result(tmp_path, "run-partial", "basic", bundle), partial, eligible)
        )
        assert record.leaderboard_valid is False

    def test_image_and_candidate_ride_the_evidence(self, tmp_path: Path, bundle) -> None:
        result = _result(tmp_path, "run-ev", "basic", bundle)
        evidence = result.evidence()
        assert evidence["candidate"]["candidate_hash"] == bundle.candidate_hash
        assert evidence["candidate"]["identity"] == bundle.identity.to_dict()
        assert evidence["candidate"]["secret_slots"] == ["ANTHROPIC_API_KEY"]
        assert evidence["image"] == {"tag": bundle.tag, "id": result.image.image_id}
        assert evidence["candidate_path"] == str(bundle.path)
        assert "ANTHROPIC_API_KEY" in evidence["secret_slots"]["bound"]

    def test_an_unverified_identity_is_refused_at_write(self, tmp_path: Path, bundle) -> None:
        import dataclasses

        from silverquillm.results_repo import InvalidRunRecordError

        result = _result(tmp_path, "run-forged", "basic", bundle)
        forged = dataclasses.replace(bundle.identity, verified=False)
        with pytest.raises(InvalidRunRecordError, match="verified"):
            write_contract_run_record(
                results_repo=tmp_path,
                run_id=result.run_id,
                candidate=forged,
                benchmark=load_benchmark("smoke"),
                mode=get_mode("basic"),
                budget_seconds=600,
                proposal_status="applied",
                eval_result=FullEvalResult(),
                evidence=result.evidence(),
            )
        assert not (tmp_path / "results").exists()

    def test_image_builder_double_is_deterministic(self, bundle) -> None:
        first, second = fake_image_builder(bundle), fake_image_builder(bundle)
        assert first == second and isinstance(first, BuiltImage)
        assert first.tag == bundle.tag and first.image_id.startswith("sha256:")
