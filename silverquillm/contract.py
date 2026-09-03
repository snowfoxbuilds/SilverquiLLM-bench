"""The Contract Run driver — a production Implementer Run driven by the bench.

One entry point — :func:`drive_contract_run` — replays TheOzolith's implementer
Run Contract (``docs/specs/BENCH-CONTRACT.md``) exactly as the production driver
does, by *consuming* ``theozolith_worker.api`` rather than re-implementing it,
over a **Candidate Bundle** whose identity the bench recomputes and never
trusts (``silverquillm.candidate``):

1. **Preflight** — refuse unless every installed the-ozolith package is the
   pinned contract (:func:`silverquillm.contract_version.check_contract_support`):
   the worker whose harness runs the agent *and* the control/nodedaemon
   packages whose verifier authenticates the candidate.
2. **Candidate** — :func:`silverquillm.candidate.load_candidate_bundle`: the
   bundle is verified through TheOzolith's verifier, its identity triple is
   recomputed, secret values are refused, and the recomputed identity must
   equal every identity the bundle records.  The bundle's secret slot *names*
   select which environment variables reach the container (values never
   appear in argv or evidence).  With a results repo configured, the vendored
   copy at ``results/<candidate-hash>/candidate/`` is written once, verified
   at write time.
3. **Image** — :func:`silverquillm.candidate.build_candidate_image`: the
   verified standalone build (private snapshot → full verification →
   ``docker build`` → deterministic tag), then the tag is resolved to the
   image ID the run launches by, after its identity labels are checked
   against the bundle.
4. **Staging** — :func:`silverquillm.jobdir.stage_job_dir` (production
   manifest with the bundle's adapter, prompt renderer, Context Tree,
   git-seeded checkout), then a trusted pre-launch snapshot of ``input/`` for
   evidence (the job dir is agent-writable from launch onward).
5. **Launch / agent** — the container is commissioned through the production
   session protocol (:func:`~theozolith_worker.api.container_session_factory`
   over :class:`~theozolith_worker.api.DockerEngine`): the image's entrypoint
   is the in-image agent harness, which launches the headless agent with the
   pointer prompt, records how it ended in ``output/status.json``, and captures
   the structured stream as ``output/transcript.txt``.  The driver waits on
   that harness-authored status — never on the outer container exit alone.
6. **Gate** — the production ``test → docs → lint`` sequence
   (:func:`~theozolith_worker.api.run_gate`) with every step submitted as a job
   over ``input/jobs/`` ↔ ``output/jobs/`` and executed by the harness *inside*
   the container.  The benchmark process never runs a candidate-authored
   command: there is no host step runner.
7. **Proposal** — ``output/proposal.json`` validated by the production
   validator; the checkout committed post-exit through the driver-owned
   repository (``run_dir/driver.git``, never the candidate's ``.git``) with the
   production commit trailer; the PR body composed via
   :func:`~theozolith_worker.api.compose_pr_body` and recorded.
8. **Harvest / evaluation** — ``workspace_final/`` from the checkout's files;
   the three-dimension Audited Eval.
9. **Record** — the lifecycle is finalized first (final phase, timing, and
   failures), ``run_dir/contract_run.json`` is written from that finalized
   evidence, and the RunRecord (when a results repo is configured) embeds *the
   same* final evidence dict under the recomputed, verified candidate identity
   — file and record agree key for key.  A run that never reached a verified
   identity (a refused preflight or candidate) has nothing to be attributed
   to: it leaves the evidence file and no record.  The record-write status
   itself lives only in the evidence file's separate ``record`` block, never
   inside the embedded snapshot, where it could only ever be stale.

Every phase runs inside one durable failure lifecycle: an exception or
non-completion anywhere is classified (:data:`FAILURE_CLASSES`), recorded with
its traceback in ``contract_run.json``, and the run still proceeds to whatever
later phases remain possible — a timed-out or crashed agent is still harvested
and graded, an evaluation crash still yields an attempted RunRecord, a record
write failure still leaves the evidence file.  ``drive_contract_run`` never
raises.  The published job dir (status, transcript, proposal, jobs channel,
checkout) is evidence and is never deleted.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import traceback
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from theozolith_worker import api

from silverquillm.candidate import (
    BuiltImage,
    CandidateBundle,
    CandidateRefusedError,
    CandidateVendorError,
    ImageBuildError,
    VendoredCandidate,
    build_candidate_image,
    load_candidate_bundle,
    vendor_candidate,
)
from silverquillm.contract_version import (
    CONTRACT_BUNDLE_FORMAT_VERSION,
    CONTRACT_IDENTITY_SPEC_VERSION,
    CONTRACT_SCHEMA_VERSION,
    InstalledDistribution,
    InstalledWorker,
    UnsupportedContractError,
    check_contract_support,
    installed_contract,
)
from silverquillm.evaluator import FullEvalResult, evaluate_run
from silverquillm.jobdir import (
    CHECKOUT_DIRNAME,
    BenchmarkRef,
    driver_git,
    stage_job_dir,
)
from silverquillm.modes import BenchmarkMode
from silverquillm.proposal import (
    PROPOSAL_APPLIED,
    LoadedProposal,
    fallback_commit_message,
    load_proposal,
)

__all__ = [
    "EVIDENCE_FILE",
    "FAILURE_CLASSES",
    "TRUSTED_INPUT_DIRNAME",
    "WORKSPACE_FINAL_DIRNAME",
    "ContractRunResult",
    "RunFailure",
    "apply_proposal",
    "container_name",
    "container_spec",
    "drive_contract_run",
    "evidence_path",
    "harvest_workspace_final",
    "read_harness_status",
    "snapshot_trusted_input",
]

# Phases, in lifecycle order.  PHASE_RECORD never enters ``phases_run``: the
# lifecycle is finalized before the record attempt (which the evidence file
# tracks in its separate ``record`` block) — the constant only tags where a
# failed record write happened.
PHASE_PREFLIGHT = "preflight"
PHASE_CANDIDATE = "candidate"
PHASE_IMAGE = "image"
PHASE_STAGING = "staging"
PHASE_LAUNCH = "launch"
PHASE_AGENT = "agent"
PHASE_GATE = "gate"
PHASE_PROPOSAL = "proposal"
PHASE_HARVEST = "harvest"
PHASE_EVALUATION = "evaluation"
PHASE_RECORD = "record"
PHASE_DONE = "done"

# Failure classes.  The agent-outcome classes (timeout, session-died, harness,
# identity) and the schema refusal mirror the production driver's uniform
# budget classes (ADR-0016/0045/0046); the rest are bench-side phases.
FAILURE_CONTRACT_UNSUPPORTED = "contract-unsupported"
FAILURE_CANDIDATE = "candidate"
FAILURE_CANDIDATE_VENDOR = "candidate-vendor"
FAILURE_IMAGE_BUILD = "image-build"
FAILURE_STAGING = "staging"
FAILURE_LAUNCH = "launch"
FAILURE_HARNESS = "harness"
FAILURE_IDENTITY = "identity"
FAILURE_SCHEMA_MISMATCH = "schema-mismatch"
FAILURE_TIMEOUT = "timeout"
FAILURE_SESSION_DIED = "session-died"
FAILURE_PROPOSAL_APPLY = "proposal-apply"
FAILURE_HARVEST = "harvest"
FAILURE_EVALUATION = "evaluation"
FAILURE_RECORD = "record"
FAILURE_DRIVER = "driver"
FAILURE_CLASSES = (
    FAILURE_CONTRACT_UNSUPPORTED,
    FAILURE_CANDIDATE,
    FAILURE_CANDIDATE_VENDOR,
    FAILURE_IMAGE_BUILD,
    FAILURE_STAGING,
    FAILURE_LAUNCH,
    FAILURE_HARNESS,
    FAILURE_IDENTITY,
    FAILURE_SCHEMA_MISMATCH,
    FAILURE_TIMEOUT,
    FAILURE_SESSION_DIED,
    FAILURE_PROPOSAL_APPLY,
    FAILURE_HARVEST,
    FAILURE_EVALUATION,
    FAILURE_RECORD,
    FAILURE_DRIVER,
)

EVIDENCE_FILE = "contract_run.json"
EVIDENCE_SCHEMA = "silverquillm.contract-run/2"
TRUSTED_INPUT_DIRNAME = "trusted_input"
WORKSPACE_FINAL_DIRNAME = "workspace_final"
PR_BODY_FILE = "pr_body.md"

# The harness anchors two pre-work refusals at the START of its status error
# (behind the session layer's "harness failed: " wrapper), exactly as the
# production driver classifies them: the Output Proposal schema refusal
# (ADR-0046, a driver/run-image skew) and the baked-identity verdict
# (ADR-0045).  Anchored, never substring — a message merely quoting a marker
# is not a verdict.  tests/test_contract_conformance.py drives the real
# harness into the schema refusal to pin the wire form.
_SESSION_WRAPPER = "harness failed: "
_SCHEMA_ERROR_PREFIX = "schema-version: "
_IDENTITY_ERROR_PREFIX = "identity: "

# The pre-launch input the driver trusts as evidence (#52 in production):
# the rendered prompt, the issue metadata, and the Context Tree surfaces.
_TRUSTED_INPUT_FILES = ("input/issue.json", api.PROMPT_FILE)
_TRUSTED_INPUT_TREES = ("input/issue", "input/pr", "input/deps")

_HARVEST_IGNORE_NAMES = frozenset({".git", "__pycache__", ".pytest_cache"})

RecordWriter = Callable[..., Path]
BundleLoader = Callable[[Path], CandidateBundle]
ImageBuilder = Callable[[CandidateBundle], BuiltImage]
CandidateVendor = Callable[[Path, CandidateBundle], VendoredCandidate]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Result / evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunFailure:
    """One classified failure: where in the lifecycle, what class, and why."""

    failure_class: str
    phase: str
    reason: str
    traceback: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "class": self.failure_class,
            "phase": self.phase,
            "reason": self.reason,
            "traceback": self.traceback,
        }


@dataclass
class ContractRunResult:
    """Everything one Contract Run produced, however far it got."""

    run_dir: Path
    run_id: str
    benchmark_id: str
    mode_name: str
    candidate_path: Path
    budget_seconds: int
    phase: str = PHASE_PREFLIGHT
    phases_run: list[str] = field(default_factory=list)
    failures: list[RunFailure] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    worker: InstalledWorker | None = None
    contract_packages: dict[str, InstalledDistribution] = field(default_factory=dict)
    bundle: CandidateBundle | None = None
    vendored: VendoredCandidate | None = None
    image: BuiltImage | None = None
    bound_slots: list[str] = field(default_factory=list)
    unbound_slots: list[str] = field(default_factory=list)
    job_dir: Path | None = None
    container: str = ""
    agent_outcome: api.AgentOutcome | None = None
    harness_status: dict[str, Any] | None = None
    transcript: dict[str, Any] | None = None
    gate: api.GateResult = field(default_factory=api.GateResult)
    proposal_status: str | None = None
    proposal_errors: list[str] = field(default_factory=list)
    commit_sha: str | None = None
    eval_result: FullEvalResult | None = None
    record_attempted: bool = False
    record_dir: Path | None = None
    record_error: str | None = None
    started_at: str = ""
    finished_at: str = ""
    agent_seconds: float | None = None

    @property
    def failure(self) -> RunFailure | None:
        """The first failure — the one that classifies the run."""
        return self.failures[0] if self.failures else None

    @property
    def failure_class(self) -> str | None:
        return self.failure.failure_class if self.failure else None

    @property
    def ok(self) -> bool:
        return not self.failures

    def record_status(self) -> dict[str, Any]:
        """The record-write status — the evidence file's separate ``record``
        block, deliberately outside :meth:`evidence`: the RunRecord embeds the
        evidence, and a record cannot truthfully describe its own write."""
        return {
            "attempted": self.record_attempted,
            "record_dir": str(self.record_dir) if self.record_dir else None,
            "error": self.record_error,
        }

    def evidence(self) -> dict[str, Any]:
        """The finalized lifecycle evidence — the ``contract_run.json`` payload
        (minus the ``record`` block) and, verbatim, the RunRecord's metadata
        source."""
        outcome = self.agent_outcome
        return {
            "schema": EVIDENCE_SCHEMA,
            "run_id": self.run_id,
            "benchmark": self.benchmark_id,
            "mode": self.mode_name,
            "candidate_path": str(self.candidate_path),
            "candidate": self.bundle.summary_dict() if self.bundle is not None else None,
            "vendored_candidate": self.vendored.to_dict() if self.vendored is not None else None,
            "image": self.image.to_dict() if self.image is not None else None,
            "secret_slots": {"bound": list(self.bound_slots), "unbound": list(self.unbound_slots)},
            "budget_seconds": self.budget_seconds,
            "container": self.container,
            "phase": self.phase,
            "phases_run": list(self.phases_run),
            "failure": self.failure.to_dict() if self.failure else None,
            "failures": [f.to_dict() for f in self.failures],
            "warnings": list(self.warnings),
            "contract_schema_version": CONTRACT_SCHEMA_VERSION,
            "contract_bundle_format_version": CONTRACT_BUNDLE_FORMAT_VERSION,
            "contract_identity_spec_version": CONTRACT_IDENTITY_SPEC_VERSION,
            "worker": self.worker.to_dict() if self.worker else None,
            "contract_packages": {
                name: dist.to_dict() for name, dist in sorted(self.contract_packages.items())
            },
            "run_dir": str(self.run_dir),
            "job_dir": str(self.job_dir) if self.job_dir else None,
            "agent_outcome": (
                {
                    "state": outcome.describe(),
                    "completed": outcome.completed,
                    "timed_out": outcome.timed_out,
                    "session_died": outcome.session_died,
                    "exit_code": outcome.exit_code,
                }
                if outcome is not None
                else None
            ),
            "harness_status": self.harness_status,
            "transcript": self.transcript,
            "gate": {
                "steps_run": list(self.gate.steps_run),
                "clean": self.gate.clean,
                "findings": [
                    {
                        "step": f.step,
                        "severity": f.severity,
                        "summary": f.summary,
                        "detail": f.detail,
                        "fixed": f.fixed,
                    }
                    for f in self.gate.findings
                ],
            },
            "proposal_status": self.proposal_status,
            "proposal_errors": list(self.proposal_errors),
            "commit_sha": self.commit_sha,
            "evaluated": self.eval_result is not None,
            "timing": {
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "agent_seconds": self.agent_seconds,
            },
        }


def _fail(
    result: ContractRunResult,
    failure_class: str,
    phase: str,
    reason: str,
    exc: BaseException | None = None,
) -> None:
    tb = "".join(traceback.format_exception(exc)) if exc is not None else ""
    result.failures.append(RunFailure(failure_class, phase, reason, tb))


def _enter(result: ContractRunResult, phase: str) -> None:
    result.phase = phase
    result.phases_run.append(phase)


def _finalize(result: ContractRunResult) -> None:
    """Stamp the final phase and timing — before the immutable record is
    built, so the record never embeds an in-flight snapshot."""
    result.finished_at = _now()
    result.phase = PHASE_DONE if result.ok else result.failure.phase


def _write_evidence(result: ContractRunResult, evidence: dict[str, Any] | None = None) -> None:
    """Write ``contract_run.json``: the lifecycle evidence (the exact dict a
    RunRecord embeds, when *evidence* is passed) plus the separate ``record``
    write-status block."""
    payload_dict = dict(result.evidence() if evidence is None else evidence)
    payload_dict["record"] = result.record_status()
    payload = json.dumps(payload_dict, indent=2, sort_keys=True) + "\n"
    try:
        api.atomic_write(result.run_dir / EVIDENCE_FILE, payload)
    except OSError as exc:  # the last resort has nowhere left to record
        result.warnings.append(f"could not write {EVIDENCE_FILE}: {exc}")


# ---------------------------------------------------------------------------
# Container spec (the production session protocol's input)
# ---------------------------------------------------------------------------


def container_name(run_id: str) -> str:
    return f"silverquillm-{run_id}"


def container_spec(
    job_dir: Path,
    *,
    image: str,
    run_id: str,
    benchmark_id: str,
    env: Mapping[str, str] | None = None,
    user: str | None = None,
) -> api.ContainerSpec:
    """The :class:`~theozolith_worker.api.ContainerSpec` for one Contract Run.

    The job dir is the only mount (at ``/job``), the image's entrypoint is the
    harness, and ``env`` values (the candidate's bound secret slots) reach
    ``docker run`` as bare ``--env NAME`` read from the engine's process
    environment — never argv.  *image* is the built image's ID.
    """
    return api.ContainerSpec(
        name=container_name(run_id),
        image=image,
        labels={"silverquillm.run-id": run_id, "silverquillm.benchmark": benchmark_id},
        mounts=((str(Path(job_dir).resolve()), api.CONTAINER_JOB_PATH),),
        env=dict(env or {}),
        user=user,
    )


# ---------------------------------------------------------------------------
# Evidence helpers
# ---------------------------------------------------------------------------


def snapshot_trusted_input(job_dir: Path, run_dir: Path) -> Path:
    """Freeze the driver-authored ``input/`` under ``run_dir/trusted_input/``
    immediately before launch: from launch onward the bind-mounted job dir is
    agent-writable, so a post-execution re-read of the prompt or Context Tree
    is never evidence."""
    job_dir, target = Path(job_dir), Path(run_dir) / TRUSTED_INPUT_DIRNAME
    if target.exists():
        shutil.rmtree(target)
    for rel in _TRUSTED_INPUT_FILES:
        src = job_dir / rel
        if src.is_file():
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target / rel)
    for rel in _TRUSTED_INPUT_TREES:
        src = job_dir / rel
        if src.is_dir():
            shutil.copytree(src, target / rel, symlinks=True)
    target.mkdir(parents=True, exist_ok=True)
    return target


def read_harness_status(job_dir: Path) -> dict[str, Any] | None:
    """``output/status.json`` exactly as the harness wrote it, or ``None``."""
    try:
        data = json.loads((Path(job_dir) / api.STATUS_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _describe_transcript(job_dir: Path) -> dict[str, Any] | None:
    path = Path(job_dir) / api.TRANSCRIPT_FILE
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return {"path": api.TRANSCRIPT_FILE, "bytes": len(data), "lines": data.count(b"\n")}


def _classify_harness_error(message: str) -> str:
    text = message.removeprefix(_SESSION_WRAPPER)
    if text.startswith(_SCHEMA_ERROR_PREFIX):
        return FAILURE_SCHEMA_MISMATCH
    if text.startswith(_IDENTITY_ERROR_PREFIX):
        return FAILURE_IDENTITY
    return FAILURE_HARNESS


# ---------------------------------------------------------------------------
# Proposal application (driver commit) and harvest
# ---------------------------------------------------------------------------


def apply_proposal(
    run_dir: Path, checkout: Path, loaded: LoadedProposal, *, run_id: str
) -> str | None:
    """Commit the checkout's files through the driver-owned repository.

    The message is the proposal's plus the production provenance trailer, or a
    generated fallback when no valid proposal shipped — the checkout is
    committed either way so the run is still graded (a bench deviation:
    production ships no fallback).  The commit is made with ``GIT_DIR`` at
    ``run_dir/driver.git``, so hooks or config the candidate planted in the
    checkout's own ``.git`` never run.  Returns the commit SHA.
    """
    if loaded.status == PROPOSAL_APPLIED:
        message = api.commit_message_with_trailer(loaded.proposal.commit_message, run_id, 0, 1)
    else:
        message = fallback_commit_message(run_id)
    driver_git(run_dir, checkout, "add", "-A")
    driver_git(run_dir, checkout, "commit", "-q", "--allow-empty", "-m", message)
    return driver_git(run_dir, checkout, "rev-parse", "HEAD").stdout.strip() or None


def _record_pr_body(run_dir: Path, loaded: LoadedProposal) -> None:
    """Compose the PR body via the production entry point and record it as
    evidence (bench runs open no PRs, so it is never applied)."""
    if loaded.status != PROPOSAL_APPLIED:
        return
    body = api.compose_pr_body(0, loaded.proposal.pr_description, loaded.proposal.section)
    (Path(run_dir) / PR_BODY_FILE).write_text(body, encoding="utf-8")


def harvest_workspace_final(
    checkout: Path, run_dir: Path, *, warnings: list[str] | None = None
) -> Path:
    """Materialize ``run_dir/workspace_final/`` from the checkout's files.

    The filesystem state of the checkout when the session ended is the sole
    source of truth for grading.  The candidate's ``.git`` and caches are left
    out (history lives in ``run_dir/driver.git``), and symlinks are never
    followed or copied — a link out of the checkout would pull host files into
    the evidence — each one skipped is reported in *warnings*.
    """
    checkout, workspace_final = Path(checkout), Path(run_dir) / WORKSPACE_FINAL_DIRNAME
    skipped: list[str] = []

    def _ignore(directory: str, names: list[str]) -> set[str]:
        ignored = {n for n in names if n in _HARVEST_IGNORE_NAMES or n.endswith(".pyc")}
        for name in names:
            if name not in ignored and os.path.islink(os.path.join(directory, name)):
                ignored.add(name)
                skipped.append(os.path.relpath(os.path.join(directory, name), checkout))
        return ignored

    if workspace_final.exists():
        shutil.rmtree(workspace_final)
    shutil.copytree(checkout, workspace_final, ignore=_ignore)
    if skipped and warnings is not None:
        warnings.append("harvest skipped symlinks: " + ", ".join(sorted(skipped)))
    return workspace_final


# ---------------------------------------------------------------------------
# The driver
# ---------------------------------------------------------------------------


def _bind_secret_slots(
    result: ContractRunResult, bundle: CandidateBundle, environ: Mapping[str, str]
) -> dict[str, str]:
    """The container environment: exactly the bundle's declared secret slots
    that are set in *environ*.  Slot names are evidence; values never are."""
    env: dict[str, str] = {}
    for slot in bundle.secret_slots:
        value = environ.get(slot)
        if value:
            env[slot] = value
            result.bound_slots.append(slot)
        else:
            result.unbound_slots.append(slot)
    if result.unbound_slots:
        result.warnings.append(
            "secret slots not set in the environment (the candidate declares them): "
            + ", ".join(result.unbound_slots)
        )
    return env


def _run_session(
    result: ContractRunResult,
    *,
    job_dir: Path,
    session_factory: api.SessionFactory,
    image: str,
    agent_env: Mapping[str, str] | None,
    container_user: str | None,
) -> None:
    """Launch, wait on the harness-authored agent outcome, replay the gate over
    the jobs channel, and shut the session down — classifying every failure."""
    _enter(result, PHASE_LAUNCH)
    try:
        manifest = api.read_manifest(job_dir)  # the stamped manifest, as staged
        spec = container_spec(
            job_dir,
            image=image,
            run_id=result.run_id,
            benchmark_id=result.benchmark_id,
            env=agent_env,
            user=container_user,
        )
        result.container = spec.name
        session = session_factory(spec, job_dir, manifest)
        session.launch()
    except Exception as exc:
        _fail(result, FAILURE_LAUNCH, PHASE_LAUNCH, f"{type(exc).__name__}: {exc}", exc)
        return
    checkout = job_dir / manifest.workdir

    started = time.monotonic()
    try:
        _enter(result, PHASE_AGENT)
        outcome: api.AgentOutcome | None = None
        try:
            outcome = session.wait_for_agent()
        except api.SessionError as exc:
            _fail(result, _classify_harness_error(str(exc)), PHASE_AGENT, str(exc), exc)
        except Exception as exc:
            _fail(result, FAILURE_HARNESS, PHASE_AGENT, f"{type(exc).__name__}: {exc}", exc)
        result.agent_seconds = round(time.monotonic() - started, 3)
        result.agent_outcome = outcome
        if outcome is not None and not outcome.completed:
            if outcome.timed_out:
                failure_class = FAILURE_TIMEOUT
            elif outcome.session_died:
                failure_class = FAILURE_SESSION_DIED
            else:
                failure_class = FAILURE_HARNESS
            _fail(result, failure_class, PHASE_AGENT, f"agent {outcome.describe()}")

        if outcome is not None and outcome.completed:
            # The production gate, every step a harness job inside the container.
            _enter(result, PHASE_GATE)
            try:
                result.gate = api.run_gate(
                    checkout,
                    runner=lambda command, timeout: session.run_job("gate", command, timeout),
                )
            except Exception as exc:
                # The agent's work is already in the checkout: grade it, with
                # the gate failure recorded as a finding (production parity).
                result.gate = api.GateResult(
                    findings=[
                        api.Finding(
                            step="gate",
                            severity="error",
                            summary=f"gate infrastructure failed: {exc}",
                        )
                    ]
                )
    finally:
        try:
            session.finish()
        except Exception as exc:
            result.warnings.append(f"session shutdown failed: {type(exc).__name__}: {exc}")


def _post_session(
    result: ContractRunResult,
    *,
    job_dir: Path,
    benchmark: BenchmarkRef,
    eval_timeout: int,
) -> None:
    """Preserve the harness outputs, apply the proposal, harvest, and grade.

    The checkout path is the one the driver *staged* — never re-read from the
    manifest, which sits in the bind-mounted job dir and is agent-writable from
    launch onward (a rewritten ``workdir`` must not redirect the commit or the
    harvest at a path of the candidate's choosing).
    """
    run_dir = result.run_dir
    checkout = job_dir / CHECKOUT_DIRNAME

    # The harness-authored outputs, preserved verbatim (they stay on disk in
    # the retained job dir; the evidence carries the status and a transcript
    # summary so a run can be diagnosed from the record alone).
    result.harness_status = read_harness_status(job_dir)
    result.transcript = _describe_transcript(job_dir)
    if result.harness_status is None:
        result.warnings.append(f"no harness-authored {api.STATUS_FILE} in the job dir")

    _enter(result, PHASE_PROPOSAL)
    loaded = load_proposal(job_dir)
    result.proposal_status = loaded.status
    result.proposal_errors = list(loaded.errors)
    if loaded.status != PROPOSAL_APPLIED:
        result.warnings.append(f"proposal {loaded.status}: {'; '.join(loaded.errors)}")
    try:
        result.commit_sha = apply_proposal(run_dir, checkout, loaded, run_id=result.run_id)
        _record_pr_body(run_dir, loaded)
    except Exception as exc:
        _fail(result, FAILURE_PROPOSAL_APPLY, PHASE_PROPOSAL, f"{type(exc).__name__}: {exc}", exc)

    _enter(result, PHASE_HARVEST)
    try:
        harvest_workspace_final(checkout, run_dir, warnings=result.warnings)
    except Exception as exc:
        _fail(result, FAILURE_HARVEST, PHASE_HARVEST, f"{type(exc).__name__}: {exc}", exc)
        return

    _enter(result, PHASE_EVALUATION)
    try:
        result.eval_result = evaluate_run(run_dir, benchmark, timeout=eval_timeout)
    except Exception as exc:
        _fail(result, FAILURE_EVALUATION, PHASE_EVALUATION, f"{type(exc).__name__}: {exc}", exc)


def _record(
    result: ContractRunResult,
    *,
    results_repo: Path | None,
    benchmark: BenchmarkRef,
    mode: BenchmarkMode,
    record_writer: RecordWriter | None,
) -> None:
    """Finalize the lifecycle, persist its evidence, then attempt the RunRecord.

    Ordering is the coherence guarantee: phase, timing, and failures are final
    *before* the record is built, one evidence dict is both written to
    ``contract_run.json`` and embedded in the record, and the record-write
    status goes only into the file's separate ``record`` block — an embedded
    write-status snapshot could never be anything but stale.  A write failure
    is itself classified and left in the evidence; no record exists then, so
    nothing diverges.  A run without a verified candidate identity is never
    recorded: there is no identity to attribute it to, and a recorded value
    is never trusted in its place.
    """
    _finalize(result)
    evidence = result.evidence()
    _write_evidence(result, evidence)  # before the attempt: a failed write is diagnosable
    if results_repo is None:
        return
    if result.bundle is None:
        result.record_error = (
            "no RunRecord: the run never reached a verified candidate identity, so"
            " there is nothing to attribute it to (the evidence file stands alone)"
        )
        result.warnings.append(result.record_error)
        _write_evidence(result, evidence)
        return
    if record_writer is None:
        from silverquillm.contract_record import write_contract_run_record

        record_writer = write_contract_run_record
    result.record_attempted = True
    try:
        result.record_dir = record_writer(
            results_repo=results_repo,
            run_id=result.run_id,
            candidate=result.bundle.identity,
            benchmark=benchmark,
            mode=mode,
            budget_seconds=result.budget_seconds,
            proposal_status=result.proposal_status,
            eval_result=result.eval_result,
            evidence=evidence,
        )
    except Exception as exc:
        result.record_error = f"{type(exc).__name__}: {exc}"
        _fail(result, FAILURE_RECORD, PHASE_RECORD, result.record_error, exc)
        _finalize(result)  # re-classify: the failed write is now the evidence
        evidence = result.evidence()
    _write_evidence(result, evidence)


def drive_contract_run(
    *,
    run_dir: Path,
    run_id: str,
    benchmark: BenchmarkRef,
    mode: BenchmarkMode,
    budget_seconds: int,
    candidate: Path,
    session_factory: api.SessionFactory,
    results_repo: Path | None = None,
    eval_timeout: int = 60,
    environ: Mapping[str, str] | None = None,
    container_user: str | None = None,
    record_writer: RecordWriter | None = None,
    bundle_loader: BundleLoader | None = None,
    image_builder: ImageBuilder | None = None,
    candidate_vendor: CandidateVendor | None = None,
) -> ContractRunResult:
    """Drive one Contract Run of the Candidate Bundle at *candidate* end to
    end; never raises.

    *session_factory* is the production seam
    (:func:`~theozolith_worker.api.container_session_factory` over a
    :class:`~theozolith_worker.api.DockerEngine` in the CLI; a harness-backed
    test double in the conformance tests).  *bundle_loader*, *image_builder*
    and *candidate_vendor* default to the real ingestion, verified build and
    vendoring (tests inject doubles for the Docker-bound build only).  The
    result's ``failures`` classify everything that went wrong;
    ``run_dir/contract_run.json`` carries the same evidence on disk.
    """
    run_dir = Path(run_dir)
    environ = os.environ if environ is None else environ
    load = bundle_loader if bundle_loader is not None else load_candidate_bundle
    build = image_builder if image_builder is not None else build_candidate_image
    vendor = candidate_vendor if candidate_vendor is not None else vendor_candidate
    result = ContractRunResult(
        run_dir=run_dir,
        run_id=run_id,
        benchmark_id=benchmark.id,
        mode_name=mode.name,
        candidate_path=Path(candidate),
        budget_seconds=budget_seconds,
        started_at=_now(),
    )
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        _enter(result, PHASE_PREFLIGHT)
        try:
            result.worker = check_contract_support()
            result.contract_packages = installed_contract()
        except UnsupportedContractError as exc:
            _fail(result, FAILURE_CONTRACT_UNSUPPORTED, PHASE_PREFLIGHT, str(exc), exc)
        else:
            if result.worker.revision is None:
                result.warnings.append(
                    "theozolith-worker records no git revision; it was authenticated"
                    " against the pinned revision by its tree digest"
                    f" (source {result.worker.source})"
                )
            _drive_candidate(
                result,
                benchmark=benchmark,
                budget_seconds=budget_seconds,
                candidate=Path(candidate),
                session_factory=session_factory,
                results_repo=results_repo,
                eval_timeout=eval_timeout,
                environ=environ,
                container_user=container_user,
                load=load,
                build=build,
                vendor=vendor,
                mode=mode,
            )
    except Exception as exc:  # a driver bug is evidence too, never an escape
        _fail(result, FAILURE_DRIVER, result.phase, f"{type(exc).__name__}: {exc}", exc)

    try:
        _record(
            result,
            results_repo=results_repo,
            benchmark=benchmark,
            mode=mode,
            record_writer=record_writer,
        )
    except Exception as exc:  # pragma: no cover - _record classifies its own failures
        _fail(result, FAILURE_DRIVER, PHASE_RECORD, f"{type(exc).__name__}: {exc}", exc)
        _finalize(result)
        _write_evidence(result)
    return result


def _drive_candidate(
    result: ContractRunResult,
    *,
    benchmark: BenchmarkRef,
    mode: BenchmarkMode,
    budget_seconds: int,
    candidate: Path,
    session_factory: api.SessionFactory,
    results_repo: Path | None,
    eval_timeout: int,
    environ: Mapping[str, str],
    container_user: str | None,
    load: BundleLoader,
    build: ImageBuilder,
    vendor: CandidateVendor,
) -> None:
    """The phases after a successful preflight: candidate, image, staging,
    session, post-session — each stopping the run on its classified failure."""
    _enter(result, PHASE_CANDIDATE)
    try:
        result.bundle = load(candidate)
    except CandidateRefusedError as exc:
        _fail(result, FAILURE_CANDIDATE, PHASE_CANDIDATE, str(exc), exc)
        return
    bundle = result.bundle
    agent_env = _bind_secret_slots(result, bundle, environ)
    if results_repo is not None:
        try:
            result.vendored = vendor(results_repo, bundle)
        except CandidateVendorError as exc:
            _fail(result, FAILURE_CANDIDATE_VENDOR, PHASE_CANDIDATE, str(exc), exc)
            return

    _enter(result, PHASE_IMAGE)
    try:
        result.image = build(bundle)
    except ImageBuildError as exc:
        _fail(result, FAILURE_IMAGE_BUILD, PHASE_IMAGE, str(exc), exc)
        return

    _enter(result, PHASE_STAGING)
    try:
        job_dir = stage_job_dir(
            result.run_dir,
            benchmark,
            mode,
            run_id=result.run_id,
            budget_seconds=budget_seconds,
            adapter=bundle.adapter,
        )
        result.job_dir = job_dir
        snapshot_trusted_input(job_dir, result.run_dir)
    except Exception as exc:
        _fail(result, FAILURE_STAGING, PHASE_STAGING, f"{type(exc).__name__}: {exc}", exc)
        return

    _run_session(
        result,
        job_dir=job_dir,
        session_factory=session_factory,
        image=result.image.image_id,
        agent_env=agent_env,
        container_user=container_user,
    )
    _post_session(result, job_dir=job_dir, benchmark=benchmark, eval_timeout=eval_timeout)


def evidence_path(run_dir: Path) -> Path:
    """Where a run's ``contract_run.json`` evidence lives."""
    return Path(run_dir) / EVIDENCE_FILE
