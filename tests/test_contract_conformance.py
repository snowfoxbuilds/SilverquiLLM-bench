"""Benchmark-owned prompt, proposal, outcome and evidence conformance."""

import copy
import json

import pytest

from silverquillm import contract
from silverquillm.evaluator import FullEvalResult
from silverquillm.modes import get_mode
from silverquillm.results_repo import read_run_record
from tests.test_contract_security import MutatingEngine
from tests.test_standalone_run import PROPOSAL, Engine, benchmark, definition, run


def test_final_record_metadata_matches_persisted_execution_evidence(tmp_path, monkeypatch):
    result, _ = run(tmp_path, monkeypatch, Engine())
    record = read_run_record(result.record_dir)
    evidence = json.loads((result.run_dir / "contract_run.json").read_text())
    for key in ("phase", "failures", "timing", "runtime_observation", "input_hashes", "gate"):
        assert record.run_metadata[key] == evidence[key]
    assert record.run_metadata["timing"]["finished_at"]


@pytest.mark.parametrize(
    "decisions,valid",
    [
        ([], False),
        ([{"what": "Keep existing behavior", "why": "It already satisfies the task."}], True),
    ],
)
def test_no_change_requires_explicit_reasoning(tmp_path, monkeypatch, decisions, valid):
    proposal = copy.deepcopy(PROPOSAL)
    proposal["fields"]["decisions"] = decisions

    def mutate(sources):
        (sources["/work"] / "answer.py").unlink()

    engine = MutatingEngine(mutate)
    engine.proposal = proposal
    result, _ = run(tmp_path, monkeypatch, engine)
    assert result.ok is valid, result.evidence()
    assert result.proposal_status == ("applied" if valid else "invalid")


def test_cleanup_failure_prevents_harvest_and_grading(tmp_path, monkeypatch):
    class Unremovable(Engine):
        def request(self, method, path, body=None, **kwargs):
            if method == "DELETE":
                raise OSError("fixture cleanup unavailable")
            return super().request(method, path, body, **kwargs)

    result, checked = run(tmp_path, monkeypatch, Unremovable())
    assert not result.ok and any(row.failure_class == "cleanup" for row in result.failures)
    assert not checked and not (result.run_dir / "workspace_final").exists()
    assert (result.run_dir / "host-state.json").exists()


def test_declared_output_schema_is_enforced(tmp_path, monkeypatch):
    candidate = definition(tmp_path)
    doc = json.loads(candidate.read_text())
    doc["runtime"]["files"][1]["schema"] = {"type": "object", "required": ["extra-required-field"]}
    candidate.write_text(json.dumps(doc))
    monkeypatch.setattr(contract, "evaluate_run", lambda *a, **kw: FullEvalResult())
    result = contract.drive_contract_run(
        run_dir=tmp_path / "run",
        run_id="run",
        candidate=candidate,
        benchmark=benchmark(tmp_path),
        mode=get_mode("basic"),
        budget_seconds=5,
        engine=Engine(),
    )
    assert result.proposal_status == "invalid"
    assert any("declared schema" in item for item in result.proposal_errors)


def test_prompt_transport_changes_preserve_historical_substantive_requirements(tmp_path):
    from pathlib import Path

    from silverquillm.workflow import Issue, render_run_prompt
    old = (Path(__file__).parent / "fixtures/legacy-implementer-prompt.txt").read_text()
    new = render_run_prompt(Issue(0, "fixture", "Implement every card"))
    for phrase in ("Implement the issue's acceptance criteria directly in the working tree.",
                   "Never stop to ask questions.", "judgment calls with rationale",
                   "Do not run git commit/push", "Do not edit `.theozolith/gate.toml`",
                   "A run with no changes and no recorded reasoning is treated as a failure."):
        assert phrase in old and phrase in new
    for field in ("commit-message", "pr-title", "pr-description", "decisions", "open-questions",
                  "remaining-work", "dead-ends", "process-issues"):
        assert field in old and field in new
    assert "format-output" not in new
    assert "no live GitHub" in new
