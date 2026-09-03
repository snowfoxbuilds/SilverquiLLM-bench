"""End-to-end harness conformance for the Contract Run — container-free.

The driver is exercised against the REAL production harness
(``tests/contract_harness.py`` runs ``theozolith-harness``'s entry point in a
thread as the "container"; ``tests/fake_claude.py`` stands in for the Claude
CLI on PATH) over a REAL Candidate Bundle (``tests/candidate_fixtures.py``
exports one through TheOzolith's export tooling; only the Docker-bound
verified build is doubled).  The full run pins every seam of the implementer
Run Contract: bundle verification and identity recomputation, the vendored
results-repo copy, the image launched by ID, prompt invocation (the adapter's
real argv with the constant pointer at the production-rendered task), the
harness-authored ``output/status.json`` and ``output/transcript.txt``, the
Output Proposal written through the real ``format-output`` CLI, gate
execution as jobs over ``input/jobs/`` ↔ ``output/jobs/`` inside the harness,
the driver commit (production trailer, driver-owned repository), harvest, the
three-dimension Audited Eval, and the RunRecord under the verified identity.
The failure-lifecycle cases prove every classified outcome — a refused
candidate, a tampered vendored copy, a failed image build, timeout, crash,
pre-work schema refusal, a harness-less container, an unpinned or locally
modified worker, an evaluation crash, a record-write failure — still yields
``contract_run.json`` evidence, with a RunRecord attempted exactly when a
verified identity exists to attribute it to.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner
from theozolith_control import candidate as ozcandidate
from theozolith_worker import api

from silverquillm import contract as contract_mod
from silverquillm import contract_version as cv
from silverquillm.candidate import ImageBuildError, load_candidate_bundle, vendor_candidate
from silverquillm.contract import (
    EVIDENCE_FILE,
    FAILURE_CANDIDATE,
    FAILURE_CANDIDATE_VENDOR,
    FAILURE_CONTRACT_UNSUPPORTED,
    FAILURE_EVALUATION,
    FAILURE_HARNESS,
    FAILURE_IDENTITY,
    FAILURE_IMAGE_BUILD,
    FAILURE_RECORD,
    FAILURE_SCHEMA_MISMATCH,
    FAILURE_SESSION_DIED,
    FAILURE_STAGING,
    FAILURE_TIMEOUT,
    PHASE_DONE,
    ContractRunResult,
    RunFailure,
    drive_contract_run,
)
from silverquillm.contract_version import (
    CONTRACT_SCHEMA_VERSION,
    PINNED_WORKER_TREE_DIGEST,
    PINNED_WORKER_VERSION,
)
from silverquillm.evaluator import FullEvalResult
from silverquillm.jobdir import driver_git_dir, load_benchmark
from silverquillm.modes import get_mode
from silverquillm.proposal import PROPOSAL_APPLIED, PROPOSAL_MISSING
from silverquillm.results_repo import OZOLITH_SCHEME, read_run_record
from tests.candidate_fixtures import (
    FAKE_ANTHROPIC_KEY,
    fake_image_builder,
    make_candidate_dir,
    rewrite_manifest,
)
from tests.contract_harness import DeadEngine, make_rig

REPO = Path(__file__).resolve().parents[1]
HOB_129 = REPO / "benchmarks" / "hob-medium" / "workspace" / "cards" / "fdn" / "fdn_129" / "card_impl.py"
SMOKE_GATE_TEST = "python3 -m pytest engine_tests/test_test_utils.py -q"
SMOKE_GATE_LINT = "python3 -m compileall -q cards engine test_utils.py"

PROPOSAL = {
    "pr-title": "Smoke targets",
    "pr-description": "Implements the smoke pool.",
    "commit-message": "Implement Leyline Axe\n\nThe reference implementation.",
}


@pytest.fixture(scope="module")
def candidate_dir(tmp_path_factory) -> Path:
    """One fixture Candidate Bundle for the module: a real export, wrapped in
    a checked-in-style ``<slug>--<hash8>/`` directory."""
    return make_candidate_dir(tmp_path_factory.mktemp("candidate"))


def _drive(tmp_path: Path, session_factory, *, run_id: str, candidate: Path, **kwargs) -> ContractRunResult:
    kwargs.setdefault("mode", get_mode("basic"))
    kwargs.setdefault("budget_seconds", 600)
    kwargs.setdefault("eval_timeout", 120)
    kwargs.setdefault("image_builder", fake_image_builder)
    kwargs.setdefault("environ", {})
    return drive_contract_run(
        run_dir=tmp_path / "run",
        run_id=run_id,
        benchmark=load_benchmark("smoke"),
        candidate=candidate,
        session_factory=session_factory,
        **kwargs,
    )


def _driver_log(run_dir: Path) -> str:
    return subprocess.run(
        ["git", "--git-dir", str(driver_git_dir(run_dir)), "log", "-1", "--format=%B"],
        capture_output=True, text=True, check=True,
    ).stdout


def _evidence(run_dir: Path) -> dict:
    return json.loads((run_dir / EVIDENCE_FILE).read_text())


@pytest.fixture
def results_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "results"
    repo.mkdir()
    return repo


@pytest.fixture
def fast_eval(monkeypatch):
    """Skip the (slow) real Audited Eval where scoring is not the point; still
    require that the harvested tree exists, as the real grader would."""
    def _stub(run_dir, benchmark, timeout=60):
        assert (Path(run_dir) / "workspace_final").is_dir()
        return FullEvalResult()

    monkeypatch.setattr(contract_mod, "evaluate_run", _stub)


class _BuilderSpy:
    def __init__(self, fail: bool = False):
        self.calls = 0
        self.fail = fail

    def __call__(self, bundle):
        self.calls += 1
        if self.fail:
            raise ImageBuildError("docker build of the candidate failed: boom")
        return fake_image_builder(bundle)


# ---------------------------------------------------------------------------
# The full implementer run through the real harness
# ---------------------------------------------------------------------------


class TestHarnessConformance:
    def test_full_implementer_run(self, tmp_path: Path, monkeypatch, results_repo: Path, candidate_dir: Path) -> None:
        invocation = tmp_path / "invocation.json"
        rig = make_rig(
            tmp_path, monkeypatch,
            playbook={
                "implement": ["129"],
                "proposal": PROPOSAL,
                "record_invocation_to": str(invocation),
            },
        )
        result = _drive(tmp_path, rig.session_factory, run_id="smoke-conformance-1",
                        candidate=candidate_dir, results_repo=results_repo)
        assert result.ok, [f.to_dict() for f in result.failures]
        assert result.phase == PHASE_DONE
        run_dir, job = result.run_dir, result.job_dir
        assert job == run_dir / "job"

        # The candidate: verified through TheOzolith's verifier, identity
        # recomputed (never trusted), vendored once into the results repo.
        bundle = result.bundle
        assert bundle is not None and bundle.path == candidate_dir
        assert candidate_dir.name.endswith(bundle.hash8)
        assert bundle.identity.scheme == OZOLITH_SCHEME and bundle.identity.verified is True
        assert result.vendored.written is True
        copy = results_repo / "results" / bundle.candidate_hash / "candidate"
        assert result.vendored.path == copy and (copy / "candidate.json").is_file()
        assert ozcandidate.verify_bundle(copy).instruction_hash == bundle.instruction_hash

        # The image: the verified build's deterministic tag, launched by ID.
        assert result.image.tag == bundle.tag
        [spec] = rig.engine.launched
        assert spec.image == result.image.image_id and spec.image.startswith("sha256:")
        assert spec.mounts == ((str(job.resolve()), "/job"),)
        # launch() clears any leftover container first, finish() removes it:
        # two removes of the one name (production ContainerSession behavior).
        assert set(rig.engine.removed) == {spec.name} and result.container == spec.name
        # No credential was set in the (empty) environment: the declared slot
        # is reported unbound by NAME, and the container got no env.
        assert result.unbound_slots == ["ANTHROPIC_API_KEY"] and spec.env == {}

        # The manifest carries the bundle's adapter verbatim.
        assert api.read_manifest(job).adapter == bundle.adapter == "claude"

        # Prompt invocation: the harness launched the adapter's real headless
        # argv — the constant pointer at the production-rendered task, never
        # the task content — in the manifest's workdir, with THEOZOLITH_JOB set.
        inv = json.loads(invocation.read_text())
        assert inv["argv"][0] == "-p"
        assert inv["flags_after_pointer"] == [
            "--dangerously-skip-permissions", "--output-format", "stream-json", "--verbose",
        ]
        assert inv["task_path"] == str(job / "input" / "prompt.md")
        assert inv["cwd"] == str(job / "checkout") and inv["job"] == str(job)
        assert inv["task_is_implementer_prompt"] and inv["task_mentions_format_output"]

        # Status: harness-authored, preserved verbatim, and the agent outcome
        # the driver records IS that status's — not the container exit.
        status = json.loads((job / "output" / "status.json").read_text())
        assert status["phase"] == "done" and status["error"] == ""
        assert status["agent"]["completed"] is True and status["agent"]["exit_code"] == 0
        assert result.harness_status == status
        assert result.agent_outcome == api.AgentOutcome(completed=True, exit_code=0)
        assert result.agent_seconds is not None

        # Transcript: the agent's structured stream, captured by the harness.
        transcript = (job / "output" / "transcript.txt").read_text()
        assert '"subtype": "init"' in transcript and '"type": "result"' in transcript
        assert result.transcript["path"] == "output/transcript.txt"
        assert result.transcript["lines"] >= 3 and result.transcript["bytes"] > 0

        # Proposal: written by the real format-output CLI, validated by the
        # production validator.
        proposal = json.loads((job / "output" / "proposal.json").read_text())
        assert proposal["schema_version"] == api.SCHEMA_VERSION and proposal["mode"] == "run"
        assert result.proposal_status == PROPOSAL_APPLIED and result.proposal_errors == []

        # Gate: the production sequence, every step a job request the harness
        # answered inside the "container", then the driver's shutdown request.
        requests = sorted(p.name for p in (job / "input" / "jobs").glob("*.json"))
        answers = sorted(p.name for p in (job / "output" / "jobs").glob("*.json"))
        assert requests == ["001-gate.json", "002-gate.json", "003-shutdown.json"]
        assert answers == ["001-gate.json", "002-gate.json"]
        first = json.loads((job / "input" / "jobs" / "001-gate.json").read_text())
        second = json.loads((job / "input" / "jobs" / "002-gate.json").read_text())
        shutdown = json.loads((job / "input" / "jobs" / "003-shutdown.json").read_text())
        assert first["command"] == SMOKE_GATE_TEST and second["command"] == SMOKE_GATE_LINT
        assert shutdown["command"] == ""
        for name in ("001-gate.json", "002-gate.json"):
            answer = json.loads((job / "output" / "jobs" / name).read_text())
            assert answer["ok"] is True and answer["exit_code"] == 0
        assert result.gate.steps_run == ["test", "lint"] and result.gate.clean

        # Driver commit: production trailer, in the driver-owned repository.
        log = _driver_log(run_dir)
        assert log.startswith("Implement Leyline Axe")
        assert "Ozolith-Run: smoke-conformance-1" in log and "Ozolith-Round: 1" in log
        assert result.commit_sha and len(result.commit_sha) == 40
        assert (run_dir / "pr_body.md").read_text().startswith("Closes #0.")

        # Harvest: the checkout's files (never its .git); the trusted input
        # snapshot taken before launch matches what was staged.
        final = run_dir / "workspace_final"
        assert (final / "cards" / "fdn" / "fdn_129" / "card_impl.py").read_bytes() == HOB_129.read_bytes()
        assert not (final / ".git").exists()
        assert (run_dir / "trusted_input" / "input" / "prompt.md").read_bytes() == (
            job / "input" / "prompt.md"
        ).read_bytes()
        assert (run_dir / "trusted_input" / "input" / "issue" / "body.md").is_file()

        # Evaluation: three dimensions from benchmarks/smoke/data/tests/audited/.
        assert result.eval_result.sos_results["fdn_129"].tests_passed >= 8
        assert result.eval_result.sos_results["fdn_129"].tests_failed == 0
        assert result.eval_result.fdn_results
        assert result.eval_result.engine_result.tests_total > 0

        # Evidence file and RunRecord carry the same coherent picture.
        evidence = _evidence(run_dir)
        assert evidence["phase"] == PHASE_DONE and evidence["failure"] is None
        assert evidence["harness_status"] == status
        assert evidence["worker"]["version"] == PINNED_WORKER_VERSION
        assert set(evidence["contract_packages"]) == {
            "theozolith-worker", "theozolith-control", "theozolith-nodedaemon", "theozolith-knowledge",
        }
        assert evidence["contract_schema_version"] == CONTRACT_SCHEMA_VERSION
        assert evidence["contract_bundle_format_version"] == 2
        assert evidence["candidate"]["candidate_hash"] == bundle.candidate_hash
        assert evidence["candidate"]["identity"] == bundle.identity.to_dict()
        assert evidence["candidate"]["path"] == str(candidate_dir)
        assert evidence["image"] == result.image.to_dict()
        assert evidence["vendored_candidate"] == {"path": str(copy), "written": True}
        assert evidence["secret_slots"] == {"bound": [], "unbound": ["ANTHROPIC_API_KEY"]}
        assert evidence["gate"]["steps_run"] == ["test", "lint"]
        assert evidence["phases_run"] == [
            "preflight", "candidate", "image", "staging", "launch", "agent", "gate",
            "proposal", "harvest", "evaluation",
        ]
        # The record-write status lives only in the file's separate block —
        # the lifecycle evidence itself never mentions its own record.
        assert evidence["record"] == {
            "attempted": True, "record_dir": str(result.record_dir), "error": None,
        }
        assert "record_dir" not in evidence and "record_error" not in evidence
        record = read_run_record(result.record_dir)
        assert result.record_dir.parent == copy.parent  # same candidate directory as the copy
        assert record.candidate == bundle.identity and record.candidate.verified is True
        assert record.benchmark == "smoke" and record.mode == "basic"
        assert record.proposal_status == PROPOSAL_APPLIED
        assert record.leaderboard_valid is False  # smoke is never leaderboard-eligible
        meta = record.run_metadata
        assert meta["harness_status"] == status
        assert meta["agent_outcome"]["completed"] is True
        assert meta["gate"]["steps_run"] == ["test", "lint"]
        assert meta["worker"]["version"] == PINNED_WORKER_VERSION
        assert meta["adapter"] == "claude" and meta["product_version"] == "0.3.0"
        assert meta["image"] == result.image.to_dict()
        assert meta["failure"] is None and meta["evaluated"] is True
        assert record.scores["card_correctness"]["evaluated"] is True
        assert record.scores["card_correctness"]["tests_passed"] >= 8
        kinds = {p["kind"]: p["location"] for p in record.artifact_pointers}
        assert kinds["run-artifacts"] == str(run_dir)
        assert kinds["contract-run-evidence"] == str(run_dir / EVIDENCE_FILE)
        assert kinds["candidate-bundle"] == f"results/{bundle.candidate_hash}/candidate/"

    def test_planned_mode_reaches_the_agent_as_the_task(self, tmp_path: Path, monkeypatch, fast_eval, candidate_dir: Path) -> None:
        invocation = tmp_path / "invocation.json"
        rig = make_rig(
            tmp_path, monkeypatch,
            playbook={"proposal": PROPOSAL, "record_invocation_to": str(invocation)},
        )
        result = _drive(tmp_path, rig.session_factory, run_id="smoke-planned", candidate=candidate_dir,
                        mode=get_mode("planned"))
        assert result.ok
        task = Path(json.loads(invocation.read_text())["task_path"]).read_text()
        assert "## Approach" in task  # the mode varied the task the agent read
        assert json.loads((result.job_dir / "input" / "manifest.json").read_text())["mode"] == "run"

    def test_record_metadata_matches_the_final_evidence_file(
        self, tmp_path: Path, monkeypatch, results_repo: Path, fast_eval, candidate_dir: Path
    ) -> None:
        """Coherence regression: on a successful run, the immutable RunRecord
        and the final ``contract_run.json`` agree key for key — the lifecycle
        (phase, timing, failures) is finalized *before* the record is built,
        and the record embeds that exact final evidence, never an in-flight
        snapshot."""
        rig = make_rig(tmp_path, monkeypatch, playbook={"implement": ["129"], "proposal": PROPOSAL})
        result = _drive(tmp_path, rig.session_factory, run_id="smoke-coherent",
                        candidate=candidate_dir, results_repo=results_repo)
        assert result.ok
        evidence = _evidence(result.run_dir)
        record = read_run_record(result.record_dir)
        meta = record.run_metadata

        assert meta["phase"] == evidence["phase"] == PHASE_DONE
        assert meta["phases_run"] == evidence["phases_run"]
        assert meta["failure"] is None and evidence["failure"] is None
        assert meta["failures"] == evidence["failures"] == []
        assert meta["timing"] == evidence["timing"]
        assert evidence["timing"]["started_at"] and evidence["timing"]["finished_at"]
        assert evidence["timing"]["finished_at"] >= evidence["timing"]["started_at"]
        assert meta["timing"]["agent_seconds"] == result.agent_seconds
        assert meta["evaluated"] is True and evidence["evaluated"] is True
        assert record.proposal_status == evidence["proposal_status"] == PROPOSAL_APPLIED
        assert meta["commit_sha"] == evidence["commit_sha"] == result.commit_sha
        assert result.commit_sha
        assert meta["worker"] == evidence["worker"]
        assert evidence["worker"]["tree_digest"] == PINNED_WORKER_TREE_DIGEST
        assert meta["image"] == evidence["image"]
        # The write status is the file's separate block, never embedded where
        # it could only be stale.
        assert evidence["record"]["record_dir"] == str(result.record_dir)
        assert "record" not in meta

    def test_secret_slots_bind_from_the_environment_by_name(
        self, tmp_path: Path, monkeypatch, fast_eval, candidate_dir: Path
    ) -> None:
        """The bundle's declared slots select which environment variables
        reach the container; the value reaches the spec (the engine passes it
        as a bare --env NAME from its own environment) and never the evidence."""
        rig = make_rig(tmp_path, monkeypatch, playbook={"proposal": PROPOSAL})
        secret = "sekrit-token-value-9f8e7d6c"
        result = _drive(tmp_path, rig.session_factory, run_id="smoke-slots", candidate=candidate_dir,
                        environ={"ANTHROPIC_API_KEY": secret, "UNRELATED": "no"})
        assert result.ok
        [spec] = rig.engine.launched
        assert spec.env == {"ANTHROPIC_API_KEY": secret}
        assert result.bound_slots == ["ANTHROPIC_API_KEY"] and result.unbound_slots == []
        evidence_text = (result.run_dir / EVIDENCE_FILE).read_text()
        assert secret not in evidence_text
        assert _evidence(result.run_dir)["secret_slots"] == {"bound": ["ANTHROPIC_API_KEY"], "unbound": []}

    def test_a_second_run_reuses_the_vendored_copy(
        self, tmp_path: Path, monkeypatch, results_repo: Path, fast_eval, candidate_dir: Path
    ) -> None:
        rig = make_rig(tmp_path, monkeypatch, playbook={"proposal": PROPOSAL})
        first = _drive(tmp_path / "a", rig.session_factory, run_id="smoke-first",
                       candidate=candidate_dir, results_repo=results_repo)
        second = _drive(tmp_path / "b", rig.session_factory, run_id="smoke-second",
                        candidate=candidate_dir, results_repo=results_repo)
        assert first.ok and second.ok
        assert first.vendored.written is True and second.vendored.written is False
        assert first.vendored.path == second.vendored.path
        assert first.record_dir.parent == second.record_dir.parent == first.vendored.path.parent


# ---------------------------------------------------------------------------
# The durable failure lifecycle
# ---------------------------------------------------------------------------


class TestFailureLifecycle:
    def test_missing_proposal_is_recorded_and_still_graded(
        self, tmp_path: Path, monkeypatch, results_repo: Path, fast_eval, candidate_dir: Path
    ) -> None:
        rig = make_rig(tmp_path, monkeypatch, playbook={"implement": ["129"]})
        result = _drive(tmp_path, rig.session_factory, run_id="smoke-noproposal",
                        candidate=candidate_dir, results_repo=results_repo)
        assert result.ok  # a missing proposal is recorded state, not a failure
        assert result.proposal_status == PROPOSAL_MISSING
        assert "no valid Output Proposal" in _driver_log(result.run_dir)
        assert result.eval_result is not None
        assert read_run_record(result.record_dir).proposal_status == PROPOSAL_MISSING

    def test_agent_timeout_is_classified_harvested_and_recorded(
        self, tmp_path: Path, monkeypatch, results_repo: Path, fast_eval, candidate_dir: Path
    ) -> None:
        rig = make_rig(
            tmp_path, monkeypatch,
            playbook={"implement": ["129"], "proposal": PROPOSAL, "hang_seconds": 30},
        )
        result = _drive(tmp_path, rig.session_factory, run_id="smoke-timeout", candidate=candidate_dir,
                        budget_seconds=1, results_repo=results_repo)
        assert result.failure_class == FAILURE_TIMEOUT and result.phase == "agent"
        # The harness killed the session and said so; the driver believed the
        # harness, not the container exit.
        assert result.agent_outcome.timed_out is True
        assert result.harness_status["agent"]["timed_out"] is True
        assert result.harness_status["phase"] == "done"
        # No gate for a non-completed session (production parity) — the only
        # job request is the driver's shutdown.
        assert result.gate.steps_run == []
        assert [p.name for p in (result.job_dir / "input" / "jobs").glob("*.json")] == ["001-shutdown.json"]
        # Still harvested, graded, and recorded, with the failure on the record.
        assert (result.run_dir / "workspace_final" / "cards" / "fdn" / "fdn_129" / "card_impl.py").is_file()
        assert result.eval_result is not None
        record = read_run_record(result.record_dir)
        assert record.run_metadata["failure"]["class"] == FAILURE_TIMEOUT
        assert record.run_metadata["agent_outcome"]["timed_out"] is True

    def test_agent_crash_is_classified(self, tmp_path: Path, monkeypatch, results_repo: Path, fast_eval, candidate_dir: Path) -> None:
        rig = make_rig(tmp_path, monkeypatch, playbook={"proposal": PROPOSAL, "exit_code": 2})
        result = _drive(tmp_path, rig.session_factory, run_id="smoke-died", candidate=candidate_dir,
                        results_repo=results_repo)
        assert result.failure_class == FAILURE_SESSION_DIED
        assert result.agent_outcome == api.AgentOutcome(session_died=True, exit_code=2)
        assert result.harness_status["agent"]["exit_code"] == 2
        assert result.gate.steps_run == []
        assert read_run_record(result.record_dir).run_metadata["failure"]["class"] == FAILURE_SESSION_DIED

    def test_schema_mismatch_is_refused_by_the_harness_pre_work(
        self, tmp_path: Path, monkeypatch, results_repo: Path, fast_eval, candidate_dir: Path
    ) -> None:
        """A driver/run-image skew: the REAL harness refuses before any session
        starts (ADR-0046) and the driver classifies its marked status error."""
        rig = make_rig(tmp_path, monkeypatch, playbook={"proposal": PROPOSAL})

        def skewed_factory(spec, job, manifest):
            raw = json.loads((job / api.MANIFEST_FILE).read_text())
            raw["schema_version"] = api.SCHEMA_VERSION + 1
            api.atomic_write(job / api.MANIFEST_FILE, json.dumps(raw))
            return rig.session_factory(spec, job, manifest)

        result = _drive(tmp_path, skewed_factory, run_id="smoke-skew", candidate=candidate_dir,
                        results_repo=results_repo)
        assert result.failure_class == FAILURE_SCHEMA_MISMATCH
        assert result.failure.reason.startswith("harness failed: schema-version: ")
        assert result.harness_status["phase"] == "failed"
        assert result.harness_status["error"].startswith("schema-version: ")
        # Strictly pre-work: no agent launched, no transcript, no gate jobs.
        assert result.agent_outcome is None and result.transcript is None
        assert list((result.job_dir / "input" / "jobs").glob("*.json")) == []
        assert result.proposal_status == PROPOSAL_MISSING
        record = read_run_record(result.record_dir)
        assert record.run_metadata["failure"]["class"] == FAILURE_SCHEMA_MISMATCH
        assert record.run_metadata["harness_status"]["phase"] == "failed"

    def test_container_without_a_harness_is_a_harness_failure(
        self, tmp_path: Path, monkeypatch, results_repo: Path, fast_eval, candidate_dir: Path
    ) -> None:
        engine = DeadEngine()
        result = _drive(tmp_path, api.container_session_factory(engine), run_id="smoke-dead",
                        candidate=candidate_dir, results_repo=results_repo)
        assert result.failure_class == FAILURE_HARNESS
        assert "exited before the agent phase completed" in result.failure.reason
        assert result.harness_status is None and result.agent_outcome is None
        assert any("status.json" in w for w in result.warnings)
        assert set(engine.removed) == {result.container}  # pre-launch clear + finish
        assert read_run_record(result.record_dir).run_metadata["failure"]["class"] == FAILURE_HARNESS

    def test_unpinned_worker_is_refused_before_anything(
        self, tmp_path: Path, monkeypatch, results_repo: Path, candidate_dir: Path
    ) -> None:
        """A refused preflight means the verifier itself is untrusted: no
        candidate is verified, so no identity exists to record under — the
        evidence file stands alone and the results repo is untouched."""
        monkeypatch.setattr(api, "SCHEMA_VERSION", CONTRACT_SCHEMA_VERSION + 1)
        engine = DeadEngine()
        builder = _BuilderSpy()
        result = _drive(tmp_path, api.container_session_factory(engine), run_id="smoke-unpinned",
                        candidate=candidate_dir, results_repo=results_repo, image_builder=builder)
        assert result.failure_class == FAILURE_CONTRACT_UNSUPPORTED
        assert "schema_version" in result.failure.reason
        assert result.phases_run == ["preflight"]
        assert result.bundle is None and builder.calls == 0
        assert result.job_dir is None and not (tmp_path / "run" / "job").exists()
        assert engine.launched == []
        assert result.record_attempted is False and result.record_dir is None
        assert "verified candidate identity" in result.record_error
        evidence = _evidence(result.run_dir)
        assert evidence["failure"]["class"] == FAILURE_CONTRACT_UNSUPPORTED
        assert evidence["record"] == {"attempted": False, "record_dir": None, "error": result.record_error}
        assert not (results_repo / "results").exists()

    def test_locally_modified_worker_never_launches(
        self, tmp_path: Path, monkeypatch, results_repo: Path, candidate_dir: Path
    ) -> None:
        """Fail closed: a worker whose installed tree does not hash to the
        pinned revision — a local edit, or an unpinned directory install — is
        refused by the real ``support_errors`` path before any verification,
        staging or launch, version and schema numbers notwithstanding."""
        tampered = cv.InstalledWorker(
            version=cv.PINNED_WORKER_VERSION,
            revision=None,
            source="file:///opt/somewhere/worker",
            tree_digest="0" * 64,
        )
        monkeypatch.setattr(cv, "installed_worker", lambda: tampered)
        engine = DeadEngine()
        result = _drive(tmp_path, api.container_session_factory(engine), run_id="smoke-tampered",
                        candidate=candidate_dir, results_repo=results_repo)
        assert result.failure_class == FAILURE_CONTRACT_UNSUPPORTED
        assert "tree digest" in result.failure.reason
        assert result.phases_run == ["preflight"] and result.phase == "preflight"
        assert result.bundle is None and result.job_dir is None
        assert engine.launched == [] and engine.removed == []
        assert result.record_attempted is False and not (results_repo / "results").exists()

    def test_a_refused_candidate_never_builds_stages_launches_or_records(
        self, tmp_path: Path, results_repo: Path, candidate_dir: Path
    ) -> None:
        """A tampered bundle (recorded instruction hash no longer matches the
        recomputed one) is a hard refusal: no image build, no job dir, no
        container, no record — and the evidence says why."""
        tampered = tmp_path / candidate_dir.name
        shutil.copytree(candidate_dir, tampered)
        rewrite_manifest(tampered / "bundle", instruction_hash="f" * 64)
        engine = DeadEngine()
        builder = _BuilderSpy()
        result = _drive(tmp_path, api.container_session_factory(engine), run_id="smoke-refused",
                        candidate=tampered, results_repo=results_repo, image_builder=builder)
        assert result.failure_class == FAILURE_CANDIDATE and result.phase == "candidate"
        assert "verification" in result.failure.reason and "recomputed" in result.failure.reason
        assert result.phases_run == ["preflight", "candidate"]
        assert result.bundle is None and builder.calls == 0
        assert result.job_dir is None and engine.launched == []
        assert result.record_attempted is False and not (results_repo / "results").exists()
        assert _evidence(result.run_dir)["failure"]["class"] == FAILURE_CANDIDATE

    def test_a_candidate_directory_with_the_wrong_hash_suffix_is_refused(
        self, tmp_path: Path, results_repo: Path, candidate_dir: Path
    ) -> None:
        renamed = tmp_path / "fixture-claude--deadbeef"
        shutil.copytree(candidate_dir, renamed)
        result = _drive(tmp_path, api.container_session_factory(DeadEngine()), run_id="smoke-suffix",
                        candidate=renamed, results_repo=results_repo)
        assert result.failure_class == FAILURE_CANDIDATE
        assert "deadbeef" in result.failure.reason and "never trusted" in result.failure.reason
        assert result.record_attempted is False

    def test_a_bundle_carrying_a_secret_value_is_refused(
        self, tmp_path: Path, results_repo: Path, candidate_dir: Path
    ) -> None:
        leaking = tmp_path / candidate_dir.name
        shutil.copytree(candidate_dir, leaking)
        rewrite_manifest(leaking / "bundle", secret_slots=[f"ANTHROPIC_API_KEY={FAKE_ANTHROPIC_KEY}"])
        result = _drive(tmp_path, api.container_session_factory(DeadEngine()), run_id="smoke-leak",
                        candidate=leaking, results_repo=results_repo)
        assert result.failure_class == FAILURE_CANDIDATE
        assert "environment-variable name" in result.failure.reason
        assert FAKE_ANTHROPIC_KEY not in (result.run_dir / EVIDENCE_FILE).read_text()

    def test_a_tampered_vendored_copy_is_refused_before_the_image_builds(
        self, tmp_path: Path, results_repo: Path, candidate_dir: Path
    ) -> None:
        """The results repo's copy must recompute to its directory: a copy
        that no longer does is a trust failure, classified before the image
        is built — the identity itself was verified, so the failure IS
        recorded under it."""
        bundle = load_candidate_bundle(candidate_dir)
        copy = vendor_candidate(results_repo, bundle).path
        (copy / "Dockerfile").write_text((copy / "Dockerfile").read_text() + "\n")
        engine = DeadEngine()
        builder = _BuilderSpy()
        result = _drive(tmp_path, api.container_session_factory(engine), run_id="smoke-vendor",
                        candidate=candidate_dir, results_repo=results_repo, image_builder=builder)
        assert result.failure_class == FAILURE_CANDIDATE_VENDOR and result.phase == "candidate"
        assert "fails verification" in result.failure.reason
        assert builder.calls == 0 and engine.launched == [] and result.job_dir is None
        record = read_run_record(result.record_dir)
        assert record.run_metadata["failure"]["class"] == FAILURE_CANDIDATE_VENDOR
        assert record.candidate == bundle.identity

    def test_image_build_failure_is_classified_and_recorded(
        self, tmp_path: Path, results_repo: Path, candidate_dir: Path
    ) -> None:
        engine = DeadEngine()
        result = _drive(tmp_path, api.container_session_factory(engine), run_id="smoke-nobuild",
                        candidate=candidate_dir, results_repo=results_repo, image_builder=_BuilderSpy(fail=True))
        assert result.failure_class == FAILURE_IMAGE_BUILD and result.phase == "image"
        assert result.phases_run == ["preflight", "candidate", "image"]
        assert result.image is None and result.job_dir is None and engine.launched == []
        assert result.vendored.written is True  # the candidate was vendored before the build
        record = read_run_record(result.record_dir)
        assert record.run_metadata["failure"]["class"] == FAILURE_IMAGE_BUILD
        assert record.run_metadata["evaluated"] is False

    def test_staging_conflict_is_classified(self, tmp_path: Path, monkeypatch, results_repo: Path, candidate_dir: Path) -> None:
        (tmp_path / "run" / "job").mkdir(parents=True)  # a prior attempt's job dir
        engine = DeadEngine()
        result = _drive(tmp_path, api.container_session_factory(engine), run_id="smoke-conflict",
                        candidate=candidate_dir, results_repo=results_repo)
        assert result.failure_class == FAILURE_STAGING
        assert "JobDirConflictError" in result.failure.reason
        assert engine.launched == []
        assert read_run_record(result.record_dir).run_metadata["failure"]["phase"] == "staging"

    def test_evaluation_exception_is_classified_and_recorded(
        self, tmp_path: Path, monkeypatch, results_repo: Path, candidate_dir: Path
    ) -> None:
        def exploding(run_dir, benchmark, timeout=60):
            raise RuntimeError("grader exploded")

        monkeypatch.setattr(contract_mod, "evaluate_run", exploding)
        rig = make_rig(tmp_path, monkeypatch, playbook={"implement": ["129"], "proposal": PROPOSAL})
        result = _drive(tmp_path, rig.session_factory, run_id="smoke-evalcrash", candidate=candidate_dir,
                        results_repo=results_repo)
        assert result.failure_class == FAILURE_EVALUATION
        assert result.eval_result is None and result.proposal_status == PROPOSAL_APPLIED
        evidence = _evidence(result.run_dir)
        assert "grader exploded" in evidence["failure"]["reason"]
        assert "RuntimeError" in evidence["failure"]["traceback"]
        assert evidence["evaluated"] is False
        record = read_run_record(result.record_dir)
        assert record.run_metadata["failure"]["class"] == FAILURE_EVALUATION
        assert all(score["evaluated"] is False for score in record.scores.values())

    def test_record_write_failure_is_classified_and_evidence_survives(
        self, tmp_path: Path, monkeypatch, fast_eval, candidate_dir: Path
    ) -> None:
        rig = make_rig(tmp_path, monkeypatch, playbook={"proposal": PROPOSAL})

        def refusing_writer(**kwargs):
            raise OSError("results repo is read-only")

        result = _drive(tmp_path, rig.session_factory, run_id="smoke-recordfail", candidate=candidate_dir,
                        results_repo=tmp_path / "results", record_writer=refusing_writer)
        assert result.failure_class == FAILURE_RECORD and result.record_dir is None
        assert result.record_error and "read-only" in result.record_error
        evidence = _evidence(result.run_dir)
        assert evidence["record"] == {
            "attempted": True, "record_dir": None, "error": result.record_error,
        }
        # No record exists, so the failed write may (and does) re-classify the
        # file's own lifecycle evidence without anything diverging.
        assert evidence["failure"]["class"] == FAILURE_RECORD
        assert evidence["phase"] == "record"
        assert evidence["proposal_status"] == PROPOSAL_APPLIED  # the run itself was fine


class TestHarnessErrorClassification:
    """The anchored status-error markers the harness uses, as production
    classifies them (a message merely quoting a marker is not a verdict)."""

    @pytest.mark.parametrize(
        ("message", "expected"),
        [
            ("harness failed: schema-version: the job manifest stamps v9", FAILURE_SCHEMA_MISMATCH),
            ("schema-version: bare", FAILURE_SCHEMA_MISMATCH),
            ("harness failed: identity: [cli-too-old] Claude Code 2.0", FAILURE_IDENTITY),
            ("harness failed: agent launch failed: quoting identity: here", FAILURE_HARNESS),
            ("run container exited before the agent phase completed", FAILURE_HARNESS),
        ],
    )
    def test_classify(self, message: str, expected: str) -> None:
        assert contract_mod._classify_harness_error(message) == expected


# ---------------------------------------------------------------------------
# CLI: `silverquillm run --candidate`
# ---------------------------------------------------------------------------


class TestRunCandidateCli:
    def _result(self, tmp_path: Path, *, failures: list[RunFailure]) -> ContractRunResult:
        return ContractRunResult(
            run_dir=tmp_path / "run", run_id="r", benchmark_id="smoke", mode_name="basic",
            candidate_path=tmp_path / "cand", budget_seconds=10, failures=failures,
            proposal_status="applied", harness_status={"phase": "done"},
            agent_outcome=api.AgentOutcome(completed=True),
        )

    def _invoke(self, tmp_path: Path, monkeypatch, result: ContractRunResult, candidate_dir: Path, *extra):
        from silverquillm.cli import main

        captured: dict = {}

        def fake_drive(**kwargs):
            captured.update(kwargs)
            return result

        monkeypatch.setattr(contract_mod, "drive_contract_run", fake_drive)
        out = CliRunner().invoke(
            main,
            ["run", "--candidate", str(candidate_dir), "--benchmark", "smoke",
             "--results-dir", str(tmp_path / "results-dir"), *extra],
        )
        return out, captured

    def test_clean_run_exits_zero_and_uses_the_production_session_factory(self, tmp_path, monkeypatch, candidate_dir):
        out, captured = self._invoke(tmp_path, monkeypatch, self._result(tmp_path, failures=[]), candidate_dir)
        assert out.exit_code == 0, out.output
        assert "Contract run complete" in out.output
        assert captured["candidate"] == candidate_dir and captured["mode"].name == "basic"
        assert captured["benchmark"].id == "smoke" and captured["budget_seconds"] == 3600
        # The production session protocol over the production docker engine;
        # secret slots bind inside the driver from the bundle's declared names.
        assert callable(captured["session_factory"])
        assert "agent_env" not in captured and "image" not in captured
        # The run dir lives under the candidate's label.
        assert captured["run_dir"].parent == tmp_path / "results-dir"
        assert captured["run_id"].startswith(f"smoke-{candidate_dir.name}-")

    def test_failed_run_exits_one_after_reporting(self, tmp_path, monkeypatch, candidate_dir):
        failed = self._result(
            tmp_path, failures=[RunFailure(FAILURE_TIMEOUT, "agent", "agent timed out")]
        )
        out, _ = self._invoke(tmp_path, monkeypatch, failed, candidate_dir)
        assert out.exit_code == 1
        assert "FAILED [timeout] at agent: agent timed out" in out.output
        assert "Contract run FAILED" in out.output

    def test_unknown_mode_is_a_usage_error(self, tmp_path, monkeypatch, candidate_dir):
        out, _ = self._invoke(tmp_path, monkeypatch, self._result(tmp_path, failures=[]), candidate_dir,
                              "--mode", "reviewer")
        assert out.exit_code != 0 and "unknown benchmark mode" in out.output

    @pytest.mark.parametrize(
        ("argv", "message"),
        [
            ([], "exactly one of --candidate"),
            (["--image", "img:x", "--benchmark", "smoke"], "belongs to --candidate"),
            (["--candidate", "{cand}", "--benchmark", "smoke", "--cards", "1"], "belongs to the legacy"),
            (["--candidate", "{cand}"], "--benchmark is required"),
            (["--candidate", "{cand}", "--image", "img:x", "--benchmark", "smoke"], "exactly one of --candidate"),
        ],
    )
    def test_the_two_lineages_do_not_mix(self, tmp_path, monkeypatch, candidate_dir, argv, message):
        from silverquillm.cli import main

        monkeypatch.setattr(contract_mod, "drive_contract_run", lambda **kw: pytest.fail("must not drive"))
        argv = [a.replace("{cand}", str(candidate_dir)) for a in argv]
        out = CliRunner().invoke(main, ["run", *argv])
        assert out.exit_code != 0 and message in out.output, out.output

    def test_run_contract_command_is_gone(self):
        from silverquillm.cli import main

        out = CliRunner().invoke(main, ["run-contract", "--help"])
        assert out.exit_code != 0
