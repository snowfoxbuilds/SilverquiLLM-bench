"""The Contract Run driver.

One entry point — :func:`drive_contract_run` — carries a candidate through the
full job-dir contract: stage the benchmark workspace and the job directory, run
the agent (a container by default, or any injected runner), harvest the final
workspace, apply the Output Proposal as a driver commit, run the three-dimension
Audited Eval, and (when a results repo is configured) write a RunRecord.

The agent step is injectable so the whole pipeline runs container-free in tests:
an ``agent_runner`` is any callable ``(workspace, output, job_dir) -> None`` that
mutates the workspace and writes ``job_dir/output/proposal.json``.

The proposal is narrative; the workspace filesystem is the evidence. A missing
or invalid proposal is recorded as ``proposal_status`` and never aborts harvest
or evaluation.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from silverquillm.evaluator import FullEvalResult, evaluate_run
from silverquillm.jobdir import BenchmarkRef, pointer_prompt, stage_job_dir
from silverquillm.modes import BenchmarkMode
from silverquillm.proposal import (
    PROPOSAL_APPLIED,
    Proposal,
    ProposalError,
    commit_message_with_trailer,
    fallback_commit_message,
    load_proposal,
)

__all__ = [
    "AgentRunner",
    "ContractRunResult",
    "apply_proposal",
    "drive_contract_run",
    "harvest_workspace_final",
    "stage_contract_workspace",
]

_STAGE_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".git")
_HARVEST_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")

_GIT_ID = ["-c", "user.name=silverquillm", "-c", "user.email=driver@silverquillm"]


class AgentRunner(Protocol):
    """Runs the agent for one Contract Run.

    Mutates *workspace* in place and writes ``job_dir/output/proposal.json``.
    The default runner launches a container; tests inject a stub.
    """

    def __call__(self, *, workspace: Path, output: Path, job_dir: Path) -> None: ...


@dataclass
class ContractRunResult:
    """The outcome of a Contract Run."""

    run_dir: Path
    proposal_status: str
    eval_result: FullEvalResult
    commit_sha: str | None = None
    record_dir: Path | None = None
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------


def stage_contract_workspace(
    staging_dir: Path, benchmark: BenchmarkRef
) -> tuple[Path, Path]:
    """Copy the benchmark's workspace into *staging_dir* and seed its git history.

    Returns ``(workspace, output)``. The workspace is git-initialized with a
    single seed commit so the driver's post-exit commit records exactly the
    agent's changes.
    """
    src = benchmark.root / "workspace"
    if not src.is_dir() or not any(src.iterdir()):
        raise FileNotFoundError(f"benchmark workspace missing or empty: {src}")

    workspace = Path(staging_dir) / "workspace"
    output = Path(staging_dir) / "output"
    if workspace.exists():
        shutil.rmtree(workspace)
    if output.exists():
        shutil.rmtree(output)

    shutil.copytree(src, workspace, ignore=_STAGE_IGNORE)
    output.mkdir(parents=True, exist_ok=True)

    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    subprocess.run(["git", *_GIT_ID, "add", "-A"], cwd=workspace, check=True)
    subprocess.run(
        ["git", *_GIT_ID, "commit", "-q", "-m", "initial workspace"],
        cwd=workspace, check=True,
    )
    return workspace, output


def harvest_workspace_final(workspace: Path, run_dir: Path) -> Path:
    """Materialize ``run_dir/workspace_final/`` from the agent's final workspace.

    The filesystem state of the workspace when the agent exits is the sole
    source of truth for grading; this snapshots it (git history included) for
    the driver commit and the Audited Eval.
    """
    workspace_final = Path(run_dir) / "workspace_final"
    if workspace_final.exists():
        shutil.rmtree(workspace_final)
    shutil.copytree(workspace, workspace_final, ignore=_HARVEST_IGNORE)
    return workspace_final


# ---------------------------------------------------------------------------
# Proposal application (driver commit)
# ---------------------------------------------------------------------------


def apply_proposal(
    workspace_final: Path,
    proposal: Proposal | ProposalError,
    *,
    run_id: str,
    benchmark: str,
    mode: str,
) -> tuple[str, str | None]:
    """Commit the harvested workspace with the proposal's message + trailer.

    Returns ``(proposal_status, commit_sha)``. On a missing/invalid proposal
    the status is ``"missing"``/``"invalid"`` and a generated fallback message
    is used — the workspace is committed either way so the run is still graded.
    The agent never runs git; the driver does.
    """
    if isinstance(proposal, Proposal):
        status = PROPOSAL_APPLIED
        message = commit_message_with_trailer(
            proposal.commit_message, run_id, benchmark, mode
        )
    else:
        status = proposal.status
        message = fallback_commit_message(run_id, benchmark, mode)

    workspace_final = Path(workspace_final)
    if not (workspace_final / ".git").is_dir():
        subprocess.run(["git", "init", "-q"], cwd=workspace_final, check=True)
    subprocess.run(["git", *_GIT_ID, "add", "-A"], cwd=workspace_final, check=True)
    commit = subprocess.run(
        ["git", *_GIT_ID, "commit", "-q", "--allow-empty", "-m", message],
        cwd=workspace_final, check=False,
    )
    commit_sha: str | None = None
    if commit.returncode == 0:
        rev = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=workspace_final,
            capture_output=True, text=True, check=False,
        )
        commit_sha = rev.stdout.strip() or None
    return status, commit_sha


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

    *agent_runner* runs the agent (default caller wires a container). When
    *results_repo* is set, a RunRecord is written via *record_writer* (defaults
    to :func:`silverquillm.contract_record.write_contract_run_record`).
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = run_dir / "_staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    try:
        workspace, output = stage_contract_workspace(staging_dir, benchmark)
        job_dir = stage_job_dir(run_dir, workspace, benchmark, mode, budget_seconds)

        # The pointer prompt the agent is launched with (constant-size).
        (workspace / "prompt.md").write_text(pointer_prompt(), encoding="utf-8")

        agent_runner(workspace=workspace, output=output, job_dir=job_dir)

        workspace_final = harvest_workspace_final(workspace, run_dir)
        proposal = load_proposal(job_dir)
        proposal_status, commit_sha = apply_proposal(
            workspace_final, proposal,
            run_id=run_id, benchmark=benchmark.id, mode=mode.name,
        )
        if isinstance(proposal, ProposalError):
            warnings.append(f"proposal {proposal.status}: {proposal.message}")

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
                proposal_status=proposal_status,
                eval_result=eval_result,
            )

        return ContractRunResult(
            run_dir=run_dir,
            proposal_status=proposal_status,
            eval_result=eval_result,
            commit_sha=commit_sha,
            record_dir=record_dir,
            warnings=warnings,
        )
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)
