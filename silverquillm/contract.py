"""Run standalone Karn Constructs through a benchmark-owned Docker/file host."""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from silverquillm import workflow as api
from silverquillm.candidate import (
    BuiltImage,
    CandidateBundle,
    VendoredCandidate,
    build_candidate_image,
    load_candidate_bundle,
    redact_credentials,
    vendor_candidate,
)
from silverquillm.decisions import section_from_dict
from silverquillm.docker_host import (
    ContainerOutcome,
    DockerEngine,
    DockerHost,
    HostError,
    container_name,
    validate_payload,
)
from silverquillm.evaluator import FullEvalResult, evaluate_run
from silverquillm.jobdir import (
    CHECKOUT_DIRNAME,
    BenchmarkRef,
    _synthetic_issue,
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
from silverquillm.safe_files import read_regular

__all__ = ["container_name"]

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
FAILURE_CONTRACT_UNSUPPORTED = "contract-unsupported"
FAILURE_CANDIDATE = "candidate"
FAILURE_CANDIDATE_VENDOR = "candidate-vendor"
FAILURE_IMAGE_BUILD = "image-build"
FAILURE_STAGING = "staging"
FAILURE_LAUNCH = "launch"
FAILURE_HARNESS = "container"
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
    "proposal",
    "cleanup",
)
EVIDENCE_FILE = "contract_run.json"
EVIDENCE_SCHEMA = "silverquillm.construct-run/1"
TRUSTED_INPUT_DIRNAME = "trusted-input"
WORKSPACE_FINAL_DIRNAME = "workspace_final"
PR_BODY_FILE = "pr_body.md"
RUNS_DIRNAME = "runs"
_UNSAFE_LABEL_CHARS = re.compile(r"[^A-Za-z0-9._-]")
_HARVEST_IGNORE_NAMES = frozenset({".git", "__pycache__", ".pytest_cache"})
RecordWriter = Callable[..., Path]


def _fail(result, failure_class, phase, reason, error=None):
    result.failures.append(RunFailure(failure_class, phase, redact_credentials(reason)))


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def candidate_label(candidate_path: Path) -> str:
    """The run-dir / run-id label for a candidate path: its directory name
    (``<slug>--<hash8>`` for a checked-in candidate), as one safe segment."""
    name = Path(candidate_path).resolve().name or "candidate"
    return _UNSAFE_LABEL_CHARS.sub("-", name).lstrip(".") or "candidate"


def new_run_name(benchmark_id: str, label: str, results_dir: Path) -> str:
    """A fresh run id ``<benchmark>-<label>-<YYYY-MM-DDThh-mm>`` that does not
    yet exist under *results_dir* (a short hex nonce disambiguates a clash) —
    the one naming rule ``silverquillm run --candidate`` and the scheduler
    share, so a run is addressable the same way whoever started it."""
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M")
    base = f"{benchmark_id}-{label}-{ts}"
    name = base
    while (Path(results_dir) / name).exists():
        name = f"{base}-{secrets.token_hex(2)}"
    return name


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
    bundle: CandidateBundle | None = None
    vendored: VendoredCandidate | None = None
    image: BuiltImage | None = None
    bound_slots: list[str] = field(default_factory=list)
    unbound_slots: list[str] = field(default_factory=list)
    job_dir: Path | None = None
    container: str = ""
    agent_outcome: ContainerOutcome | None = None
    runtime_observation: dict[str, Any] | None = None
    input_hashes: dict[str, str] = field(default_factory=dict)
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
            "benchmark_interface_version": 1,
            "definition_version": self.bundle.manifest["definition_version"]
            if self.bundle
            else None,
            "input_hashes": dict(self.input_hashes),
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
            "runtime_observation": self.runtime_observation,
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


def evidence_path(run_dir: Path) -> Path:
    """Where a run's ``contract_run.json`` evidence lives."""
    return Path(run_dir) / EVIDENCE_FILE


def drive_contract_run(
    *,
    run_dir,
    run_id,
    benchmark,
    mode,
    budget_seconds,
    candidate,
    results_repo=None,
    container_user=None,
    environ=None,
    eval_timeout=60,
    bundle_loader=None,
    image_builder=None,
    candidate_vendor=None,
    record_writer=None,
    engine=None,
    host_factory=DockerHost,
):
    result = ContractRunResult(
        Path(run_dir), run_id, benchmark.id, mode.name, Path(candidate), budget_seconds
    )
    result.started_at = _now()
    result.run_dir.mkdir(parents=True, exist_ok=True)
    host = None
    cleanup_confirmed = False
    loaded = None
    interrupted = None
    redactions = ()

    def redact(value):
        for secret in redactions:
            value = value.replace(secret, "[redacted credential]")
        return value

    def redact_data(value):
        if isinstance(value, str):
            return redact(value)
        if isinstance(value, list):
            return [redact_data(item) for item in value]
        if isinstance(value, dict):
            return {key: redact_data(item) for key, item in value.items()}
        return value

    try:
        if type(budget_seconds) is not int or budget_seconds <= 0:
            raise HostError("benchmark budget must be a positive integer")
        _enter(result, PHASE_CANDIDATE)
        result.bundle = (bundle_loader or load_candidate_bundle)(Path(candidate))
        document = result.bundle.manifest
        _enter(result, PHASE_PREFLIGHT)
        DockerHost.admit(document)
        if results_repo is not None:
            result.vendored = (candidate_vendor or vendor_candidate)(
                Path(results_repo), result.bundle
            )
        _enter(result, PHASE_IMAGE)
        engine = engine or DockerEngine()
        result.image = (
            image_builder or (lambda item: build_candidate_image(item, inspector=engine.image))
        )(result.bundle)
        _enter(result, PHASE_STAGING)
        job = stage_job_dir(
            result.run_dir,
            benchmark,
            mode,
            run_id=run_id,
            budget_seconds=budget_seconds,
            adapter="configured",
        )
        result.job_dir = job
        selected_env = os.environ if environ is None else environ
        redactions = tuple(
            sorted(
                {
                    selected_env[key]
                    for key in result.bundle.secret_slots
                    if isinstance(selected_env.get(key), str) and selected_env[key]
                },
                key=len,
                reverse=True,
            )
        )
        result.bound_slots = [key for key in result.bundle.secret_slots if selected_env.get(key)]
        result.unbound_slots = [
            key for key in result.bundle.secret_slots if not selected_env.get(key)
        ]
        if result.unbound_slots:
            raise HostError("required raw-secret bindings are unavailable")
        host = host_factory(
            document,
            result.image.image_id,
            result.run_dir,
            job,
            engine=engine,
            environ=selected_env,
            user=container_user,
            run_id=run_id,
        )
        issue = _synthetic_issue(benchmark, mode)
        host.prepare(
            lambda input_path, proposal_path: api.render_run_prompt(
                issue, input_path=input_path, proposal_path=proposal_path
            ),
            {
                "version": 1,
                "run_id": run_id,
                "benchmark": benchmark.id,
                "mode": mode.name,
                "budget_seconds": budget_seconds,
            },
        )
        result.input_hashes = dict(host.input_hashes)
        _enter(result, PHASE_LAUNCH)
        started = time.monotonic()
        outcome = host.run(budget_seconds)
        result.agent_seconds = round(time.monotonic() - started, 3)
        result.agent_outcome = outcome
        result.container = host.container["name"]
        result.runtime_observation = {
            "engine_id": host.engine_id,
            "uid": host.uid,
            "gid": host.gid,
            "backend": "docker",
            "network": document["runtime"]["network"],
            "resources": document["runtime"]["resources"],
            "bootstrap": document["runtime"]["bootstrap"] is not None,
            "initializer": document["runtime"]["initializer"] is not None,
            "native_tool_observation": None,
            "model_observation": None,
        }
        _enter(result, PHASE_AGENT)
        if not outcome.completed:
            _fail(
                result,
                FAILURE_TIMEOUT if outcome.timed_out else FAILURE_HARNESS,
                PHASE_AGENT,
                "container timed out" if outcome.timed_out else "container exited unsuccessfully",
            )
        if outcome.completed:
            _enter(result, PHASE_GATE)
            try:
                result.gate = api.run_gate(job / CHECKOUT_DIRNAME, runner=host.gate)
            except Exception as error:
                result.gate = api.GateResult(
                    findings=[
                        api.Finding(
                            "gate",
                            "error",
                            "isolated gate infrastructure failed",
                            host.redact(str(error)),
                        )
                    ]
                )
            result.runtime_observation["gate_image_id"] = host.gate_image
        _enter(result, PHASE_PROPOSAL)
        proposal_path = host.files["proposal"]
        loaded = load_proposal(job, path=proposal_path)
        if loaded.status == PROPOSAL_APPLIED:
            declaration = next(
                row for row in document["runtime"]["files"] if row["name"] == "proposal"
            )
            try:
                validate_payload(declaration["schema"], json.loads(read_regular(proposal_path)))
            except Exception:
                loaded = LoadedProposal(
                    "invalid", None, ["proposal does not match its declared schema"]
                )
        result.proposal_status = loaded.status
        result.proposal_errors = list(loaded.errors)
        if loaded.status != PROPOSAL_APPLIED:
            _fail(
                result, "proposal", PHASE_PROPOSAL, "missing or invalid benchmark Output Proposal"
            )
    except BaseException as error:
        if not isinstance(error, Exception):
            interrupted = error
        reason = (
            "benchmark interrupted"
            if interrupted is not None
            else host.redact(str(error))
            if host is not None
            else str(error)
        )
        failure = FAILURE_CONTRACT_UNSUPPORTED if result.phase == PHASE_PREFLIGHT else result.phase
        if failure not in FAILURE_CLASSES:
            failure = FAILURE_DRIVER
        _fail(result, failure, result.phase, reason)
    finally:
        if host is not None:
            try:
                host.finish()
                cleanup_confirmed = True
            except Exception as error:
                _fail(result, "cleanup", result.phase, host.redact(str(error)))
        if (
            result.job_dir is not None
            and result.agent_outcome is not None
            and cleanup_confirmed
            and interrupted is None
        ):
            checkout = result.job_dir / CHECKOUT_DIRNAME
            if loaded is None:
                loaded = LoadedProposal("missing", None, ["no observed proposal"])
            try:
                if loaded.status == PROPOSAL_APPLIED:
                    section = section_from_dict(redact_data(asdict(loaded.proposal.section)))
                    section.gate_findings = list(result.gate.findings)
                    loaded = replace(
                        loaded,
                        proposal=replace(
                            loaded.proposal,
                            commit_message=redact(loaded.proposal.commit_message),
                            pr_title=redact(loaded.proposal.pr_title),
                            pr_description=redact(loaded.proposal.pr_description),
                            section=section,
                        ),
                    )
                    driver_git(result.run_dir, checkout, "add", "-A")
                    unchanged = (
                        driver_git(
                            result.run_dir, checkout, "diff", "--cached", "--quiet", check=False
                        ).returncode
                        == 0
                    )
                    if unchanged and not loaded.proposal.section.decisions:
                        loaded = LoadedProposal(
                            "invalid",
                            None,
                            ["unchanged checkout needs recorded no-change reasoning"],
                        )
                        result.proposal_status = loaded.status
                        result.proposal_errors = list(loaded.errors)
                        _fail(result, "proposal", PHASE_PROPOSAL, loaded.errors[0])
                result.commit_sha = apply_proposal(result.run_dir, checkout, loaded, run_id=run_id)
                _record_pr_body(result.run_dir, loaded)
            except Exception as error:
                _fail(result, FAILURE_PROPOSAL_APPLY, PHASE_PROPOSAL, str(error))
            _enter(result, PHASE_HARVEST)
            try:
                harvest_workspace_final(checkout, result.run_dir, warnings=result.warnings)
                _enter(result, PHASE_EVALUATION)
                result.eval_result = evaluate_run(result.run_dir, benchmark, timeout=eval_timeout)
            except Exception as error:
                _fail(result, FAILURE_EVALUATION, PHASE_EVALUATION, str(error))
        result.warnings = [redact(value) for value in result.warnings]
        result.proposal_errors = [redact(value) for value in result.proposal_errors]
        result.failures = [
            replace(value, reason=redact(value.reason), traceback=redact(value.traceback))
            for value in result.failures
        ]
        result.gate.findings = [
            replace(value, summary=redact(value.summary), detail=redact(value.detail))
            for value in result.gate.findings
        ]
        _record(
            result,
            results_repo=results_repo,
            benchmark=benchmark,
            mode=mode,
            record_writer=record_writer,
        )
    if interrupted is not None:
        raise interrupted
    return result
