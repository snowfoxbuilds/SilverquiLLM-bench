"""The Contract Run driver — a production Implementer Run with the bench driver.

One entry point — :func:`drive_contract_run` — replays TheOzolith's implementer
Run Contract (BENCH-CONTRACT.md): stage the production job directory (via
:func:`silverquillm.jobdir.stage_job_dir`), run the agent (a container by
default, or any injected runner) with the in-image contract, replay the
production ``test → docs → lint`` gate over the jobs channel, validate the
Output Proposal with the *production* validator and apply it post-exit as the
driver commit (agent never runs git), harvest the checkout, run the
three-dimension Audited Eval, and (when a results repo is configured) write a
RunRecord carrying the execution outcome.

Every driver behavior the contract exposes is *consumed* from
``theozolith_worker.api`` (prompt renderer, manifest, proposal validation, PR
body, gate sequence, commit trailer), never re-implemented — so bench evidence
cannot drift from production.

The agent step is injectable so the whole pipeline runs container-free in tests:
an ``agent_runner`` is any callable ``(job_dir) -> AgentOutcome`` that works in
``job_dir/checkout`` and writes ``job_dir/output/proposal.json``.

The proposal is narrative; the checkout filesystem is the evidence.  A missing
or invalid proposal, a timeout, or a non-zero exit is recorded and never aborts
harvest or evaluation.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from theozolith_worker import api

from silverquillm.evaluator import FullEvalResult, evaluate_run
from silverquillm.jobdir import BenchmarkRef, stage_job_dir
from silverquillm.modes import BenchmarkMode
from silverquillm.proposal import (
    PROPOSAL_APPLIED,
    fallback_commit_message,
    load_proposal,
)

__all__ = [
    "AgentRunner",
    "ContractRunResult",
    "apply_proposal",
    "drive_contract_run",
    "harvest_workspace_final",
    "subprocess_step_runner",
]

_HARVEST_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
_GIT_ID = ["-c", "user.name=silverquillm", "-c", "user.email=driver@silverquillm"]


class AgentRunner(Protocol):
    """Runs the agent for one Contract Run.

    Works in ``job_dir/checkout`` and writes ``job_dir/output/proposal.json``,
    then returns how the agent process ended.  The default runner launches a
    container; tests inject a stub.
    """

    def __call__(self, *, job_dir: Path) -> api.AgentOutcome: ...


@dataclass
class ContractRunResult:
    """The outcome of a Contract Run."""

    run_dir: Path
    proposal_status: str
    eval_result: FullEvalResult
    agent_outcome: api.AgentOutcome
    gate: api.GateResult
    commit_sha: str | None = None
    record_dir: Path | None = None
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Gate (production sequence over the checkout)
# ---------------------------------------------------------------------------


def subprocess_step_runner(checkout: Path):
    """A :data:`~theozolith_worker.api` gate ``StepRunner`` that runs each step
    command in the checkout.  Gate steps run agent-authored code; the benchmark
    checkout is the sandbox (the driver never runs repository code elsewhere)."""

    def _run(command: str, timeout: float) -> tuple[bool, str]:
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=checkout,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return False, f"gate step timed out after {timeout:g}s"
        return proc.returncode == 0, proc.stdout + proc.stderr

    return _run


# ---------------------------------------------------------------------------
# Proposal application (driver commit)
# ---------------------------------------------------------------------------


def apply_proposal(checkout: Path, loaded, *, run_id: str) -> str | None:
    """Commit the checkout with the proposal's message + production trailer.

    On a missing/invalid proposal a generated fallback message is used — the
    checkout is committed either way so the run is still graded.  Returns the
    commit SHA (or ``None`` if the commit failed).  The agent never runs git.
    """
    if loaded.status == PROPOSAL_APPLIED:
        message = api.commit_message_with_trailer(
            loaded.proposal.commit_message, run_id, 0, 1
        )
    else:
        message = fallback_commit_message(run_id)

    checkout = Path(checkout)
    if not (checkout / ".git").is_dir():
        subprocess.run(["git", "init", "-q"], cwd=checkout, check=True)
    subprocess.run(["git", *_GIT_ID, "add", "-A"], cwd=checkout, check=True)
    commit = subprocess.run(
        ["git", *_GIT_ID, "commit", "-q", "--allow-empty", "-m", message],
        cwd=checkout,
        check=False,
    )
    if commit.returncode != 0:
        return None
    rev = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        capture_output=True,
        text=True,
        check=False,
    )
    return rev.stdout.strip() or None


def _record_pr_body(run_dir: Path, loaded) -> None:
    """Compose the PR body via the production entry point and record it as
    evidence (bench runs open no PRs, so it is never applied)."""
    if loaded.status != PROPOSAL_APPLIED:
        return
    body = api.compose_pr_body(0, loaded.proposal.pr_description, loaded.proposal.section)
    (Path(run_dir) / "pr_body.md").write_text(body, encoding="utf-8")


def harvest_workspace_final(checkout: Path, run_dir: Path) -> Path:
    """Materialize ``run_dir/workspace_final/`` from the committed checkout.

    The filesystem state of the checkout when the agent exits (and the driver
    commits) is the sole source of truth for grading; this snapshots it (git
    history included) for the Audited Eval.
    """
    workspace_final = Path(run_dir) / "workspace_final"
    if workspace_final.exists():
        shutil.rmtree(workspace_final)
    shutil.copytree(checkout, workspace_final, ignore=_HARVEST_IGNORE)
    return workspace_final


# ---------------------------------------------------------------------------
# The driver
# ---------------------------------------------------------------------------


def drive_contract_run(
    *,
    run_dir: Path,
    run_id: str,
    benchmark: BenchmarkRef,
    mode: BenchmarkMode,
    budget_seconds: int,
    agent_runner: AgentRunner,
    results_repo: Path | None = None,
    image: str | None = None,
    eval_timeout: int = 60,
    record_writer: Callable[..., Path] | None = None,
) -> ContractRunResult:
    """Drive one Contract Run end to end and return its :class:`ContractRunResult`.

    Staging is atomic; the published job dir is evidence and is never deleted, so
    a timeout, a non-zero exit, an evaluation error, or a RunRecord write failure
    all leave the checkout, job output, and logs on disk for diagnosis.
    """
    run_dir = Path(run_dir)
    warnings: list[str] = []

    job_dir = stage_job_dir(
        run_dir, benchmark, mode, run_id=run_id, budget_seconds=budget_seconds
    )
    checkout = job_dir / "checkout"

    # Run the agent (container or injected stub); record how the process ended.
    # (The harness-written output/status.json — a more authoritative source — is
    # a #65 concern: genuine harness-as-PID-1 runs land with the derived images.)
    runner_outcome = agent_runner(job_dir=job_dir)
    outcome = runner_outcome if runner_outcome is not None else api.AgentOutcome(completed=True)
    if not outcome.completed:
        warnings.append(f"agent {outcome.describe()}; harvesting and grading anyway")

    # Replay the production gate (test -> docs -> lint) over the checkout.
    gate = api.run_gate(checkout, subprocess_step_runner(checkout))
    gate_errors = [f.summary for f in gate.findings if f.severity == "error"]
    if gate_errors:
        warnings.append("gate findings: " + "; ".join(gate_errors))

    # Validate with the production validator; commit post-exit; record evidence.
    loaded = load_proposal(job_dir)
    if loaded.status != PROPOSAL_APPLIED:
        warnings.append(f"proposal {loaded.status}: {'; '.join(loaded.errors)}")
    commit_sha = apply_proposal(checkout, loaded, run_id=run_id)
    _record_pr_body(run_dir, loaded)

    harvest_workspace_final(checkout, run_dir)
    eval_result = evaluate_run(run_dir, benchmark, timeout=eval_timeout)

    record_dir: Path | None = None
    if results_repo is not None:
        if record_writer is None:
            from silverquillm.contract_record import write_contract_run_record

            record_writer = write_contract_run_record
        record_dir = record_writer(
            results_repo=results_repo,
            run_id=run_id,
            image=image,
            benchmark=benchmark,
            mode=mode,
            budget_seconds=budget_seconds,
            proposal_status=loaded.status,
            eval_result=eval_result,
            agent_outcome=outcome,
            gate=gate,
            run_dir=run_dir,
        )

    return ContractRunResult(
        run_dir=run_dir,
        proposal_status=loaded.status,
        eval_result=eval_result,
        agent_outcome=outcome,
        gate=gate,
        commit_sha=commit_sha,
        record_dir=record_dir,
        warnings=warnings,
    )
