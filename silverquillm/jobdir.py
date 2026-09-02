"""Job-directory staging: the bench replays TheOzolith's implementer Run Contract.

A Contract Run drives a candidate through the *same* on-disk seam the production
substrate uses (BENCH-CONTRACT.md; ADR-0013/0019/0046): a per-run job directory
mounted at ``/job`` holding the manifest, the driver-rendered task, the Context
Tree, the checked-out repo the agent works in, and the ``output/`` slot where it
writes its Output Proposal.  Benchmark evidence transfers by construction because
the bench does not imitate the contract — it *consumes* TheOzolith's published
entry points (``theozolith_worker.api``), so nothing here can drift from
production as the templates evolve.

What :func:`stage_job_dir` materializes (all via the published API):

- ``input/manifest.json`` — a production :class:`~theozolith_worker.api.Manifest`
  (``mode: "run"``, ``round: 1``, stamped ``schema_version``, ``workdir:
  "checkout"``) written with :func:`~theozolith_worker.api.write_manifest`.  The
  real ``read_manifest`` rejects unknown keys, so the Benchmark Mode never rides
  the manifest — it lives on the RunRecord and shapes only the synthetic task.
- ``input/prompt.md`` — the production implementer prompt, byte-for-byte from
  :func:`~theozolith_worker.api.render_run_prompt` (the task rides the synthetic
  issue body it wraps, never a bench-authored template).
- ``input/issue.json`` + ``input/issue/`` — the synthetic GitHub-style issue and
  its Context Tree, the latter via :func:`~theozolith_worker.api.write_tree`.
- ``checkout/`` — the benchmark workspace, git-initialized with a seed commit so
  the driver's post-exit commit records exactly the agent's changes.
- ``output/`` — empty; the agent writes ``output/proposal.json`` there.

Staging is atomic and retry-safe: the whole tree is built in a private sibling
and published with a single :func:`os.replace`, and an existing job dir is a
loud conflict — a retry can never inherit a prior attempt's proposal, status,
or checkout.

Public API
----------
- :class:`BenchmarkRef` — a resolved, runnable benchmark.
- :func:`load_benchmark` — resolve ``benchmarks/<id>/config.json``.
- :func:`stage_job_dir` — build ``run_dir/job/`` for one Contract Run.
- :func:`pointer_prompt` — the constant-size launch pointer (interim images).
- :class:`BenchmarkNotRunnableError` / :class:`BenchmarkNotFoundError`
  / :class:`JobDirConflictError`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from theozolith_worker import api

from silverquillm.modes import BenchmarkMode

__all__ = [
    "CHECKOUT_DIRNAME",
    "CONTAINER_JOB_PATH",
    "BenchmarkNotFoundError",
    "BenchmarkNotRunnableError",
    "BenchmarkRef",
    "JobDirConflictError",
    "load_benchmark",
    "pointer_prompt",
    "stage_job_dir",
]

_REPO_ROOT = Path(__file__).resolve().parent.parent

#: Where the job directory is bind-mounted inside the container (substrate parity).
CONTAINER_JOB_PATH = api.CONTAINER_JOB_PATH  # "/job"

#: The manifest's ``workdir`` — the agent's working directory, ``/job/checkout``.
CHECKOUT_DIRNAME = "checkout"

_SEED_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".git")
_GIT_ID = ["-c", "user.name=silverquillm", "-c", "user.email=driver@silverquillm"]

_SAFE_SEGMENT_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def pointer_prompt() -> str:
    """The constant, constant-size pointer an interim image may be launched with.

    Production's harness passes this on argv (never task content — the full task
    rides ``input/prompt.md``); the interim ``--image`` path forwards it via the
    environment for candidate images that read it.  Genuine harness-as-PID-1
    delivery lands with the Candidate-Bundle derived images (#65).
    """
    path = f"{CONTAINER_JOB_PATH}/{api.PROMPT_FILE}"
    return (
        f"Work on the task specified in {path}. Read that file first — it is "
        "your complete assignment — then execute it exactly."
    )


class BenchmarkNotRunnableError(Exception):
    """A benchmark exists but cannot be run (e.g. an empty card pool)."""


class BenchmarkNotFoundError(BenchmarkNotRunnableError):
    """No benchmark with the requested id (message lists the available ones)."""


class JobDirConflictError(Exception):
    """A job dir already exists where a fresh Contract Run would be staged."""


@dataclass(frozen=True)
class BenchmarkRef:
    """A resolved benchmark: its id, on-disk root, and parsed ``config.json``."""

    id: str
    root: Path
    config: dict[str, Any]

    @property
    def display_name(self) -> str:
        name = self.config.get("display_name")
        return name if isinstance(name, str) and name else self.id

    @property
    def target_set(self) -> str:
        """The lowercased target set code — the ``cards/<set>/`` subdirectory
        the agent fills in and the ``audited/<set>/`` grader suite key."""
        draft = self.config.get("draft_set")
        code = draft.get("primary_set_code") if isinstance(draft, dict) else None
        if not isinstance(code, str) or not code:
            raise BenchmarkNotRunnableError(
                f"benchmark {self.id!r} config has no draft_set.primary_set_code"
            )
        return code.lower()

    @property
    def cards(self) -> list[str]:
        cards = self.config.get("cards")
        return [str(c) for c in cards] if isinstance(cards, list) else []


def _available_benchmarks(repo_root: Path) -> list[str]:
    root = repo_root / "benchmarks"
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if (p / "config.json").is_file())


def load_benchmark(bench_id: str, *, repo_root: Path | None = None) -> BenchmarkRef:
    """Resolve *bench_id* to a runnable :class:`BenchmarkRef`.

    Raises :class:`BenchmarkNotFoundError` (listing the available benchmarks)
    for an unknown id, and :class:`BenchmarkNotRunnableError` when the benchmark
    exists but its card pool is empty — both are ``BenchmarkNotRunnableError``,
    so a caller can refuse an un-runnable benchmark with one ``except``.
    """
    repo_root = repo_root or _REPO_ROOT
    if not isinstance(bench_id, str) or not _SAFE_SEGMENT_RE.match(bench_id):
        raise BenchmarkNotFoundError(
            f"invalid benchmark id {bench_id!r}; "
            f"available: {', '.join(_available_benchmarks(repo_root)) or '(none)'}"
        )
    config_path = repo_root / "benchmarks" / bench_id / "config.json"
    if not config_path.is_file():
        available = _available_benchmarks(repo_root)
        raise BenchmarkNotFoundError(
            f"unknown benchmark {bench_id!r}; "
            f"available: {', '.join(available) or '(none)'}"
        )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise BenchmarkNotRunnableError(f"{config_path} is not a JSON object")
    recorded = config.get("id")
    if recorded is not None and recorded != bench_id:
        raise BenchmarkNotRunnableError(
            f"config.json id {recorded!r} != requested benchmark {bench_id!r}"
        )
    ref = BenchmarkRef(id=bench_id, root=config_path.parent, config=config)
    if not ref.cards:
        raise BenchmarkNotRunnableError(
            f"benchmark {bench_id!r} has an empty card pool; nothing to run "
            "(picks have not landed yet)"
        )
    return ref


# ---------------------------------------------------------------------------
# Synthetic task (the issue the production prompt renderer wraps)
# ---------------------------------------------------------------------------


def _pool_names(benchmark: BenchmarkRef) -> dict[str, str]:
    """Best-effort {normalized collector number -> card name} from ``pool.json``."""
    pool_path = benchmark.root / "data" / "pool.json"
    if not pool_path.is_file():
        return {}
    try:
        pool = json.loads(pool_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    names: dict[str, str] = {}
    if isinstance(pool, list):
        for entry in pool:
            if not isinstance(entry, dict):
                continue
            cn = entry.get("collector_number")
            name = entry.get("name")
            if isinstance(cn, str) and isinstance(name, str):
                names[_norm_cn(cn)] = name
    return names


def _norm_cn(cn: str) -> str:
    return str(int(cn)) if cn.isdigit() else cn


def _issue_body(benchmark: BenchmarkRef, mode: BenchmarkMode) -> str:
    """The synthetic issue body: the problem statement plus the mode's addendum.

    The production prompt renderer wraps this verbatim; the Benchmark Mode's
    only prompt-side effect is this task-synthesis variation.
    """
    set_code = benchmark.config.get("draft_set", {}).get("primary_set_code", "")
    names = _pool_names(benchmark)
    lines = [
        (
            f"Implement every card in the {benchmark.display_name} problem set. "
            f"Each target card below ships as a stub `card_impl.py` under "
            f"`cards/{benchmark.target_set}/`; complete each one so its behavior "
            "matches its spec and the game rules."
        ),
        "",
        "## Target cards",
        "",
    ]
    for cn in benchmark.cards:
        name = names.get(_norm_cn(cn))
        label = f"`{set_code} #{cn}`" if set_code else f"`#{cn}`"
        lines.append(f"- {label}" + (f" — {name}" if name else ""))
    return "\n".join(lines) + mode.issue_addendum


def _synthetic_issue(benchmark: BenchmarkRef, mode: BenchmarkMode) -> Any:
    """A synthetic GitHub-style :class:`~theozolith_worker.api.Issue`."""
    return api.Issue(
        number=0,
        title=f"Implement the {benchmark.display_name} card pool",
        body=_issue_body(benchmark, mode),
        labels=set(),
        assignees=[],
        is_pr=False,
    )


def _write_issue_metadata(job: Path, issue: Any) -> None:
    """``input/issue.json`` in the production driver's shape (round-one)."""
    api.atomic_write(
        job / "input" / "issue.json",
        json.dumps(
            {
                "number": issue.number,
                "title": issue.title,
                "body": issue.body,
                "labels": sorted(issue.labels),
                "round": 1,
            },
            indent=2,
            sort_keys=True,
        ),
    )


def _git_init_seed(checkout: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=checkout, check=True)
    subprocess.run(["git", *_GIT_ID, "add", "-A"], cwd=checkout, check=True)
    subprocess.run(
        ["git", *_GIT_ID, "commit", "-q", "-m", "initial checkout"],
        cwd=checkout,
        check=True,
    )


def stage_job_dir(
    run_dir: Path,
    benchmark: BenchmarkRef,
    mode: BenchmarkMode,
    *,
    run_id: str,
    budget_seconds: int,
) -> Path:
    """Stage ``run_dir/job/`` for one Contract Run and return the job dir.

    Builds the entire tree — manifest, prompt, issue metadata, Context Tree, the
    git-seeded ``checkout/``, and an empty ``output/`` — in a private sibling and
    publishes it with a single atomic rename.  An existing ``run_dir/job`` is a
    loud :class:`JobDirConflictError`: a fresh or retried run never inherits a
    prior attempt's proposal, status, transcript, or checkout.
    """
    run_dir = Path(run_dir)
    job = run_dir / "job"
    if job.exists():
        raise JobDirConflictError(
            f"a job dir already exists at {job}; a Contract Run never overwrites "
            "another attempt's job directory (stage into a fresh run dir)"
        )
    src = benchmark.root / "workspace"
    if not src.is_dir() or not any(src.iterdir()):
        raise FileNotFoundError(f"benchmark workspace missing or empty: {src}")

    run_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=run_dir, prefix=".job-staging-"))
    try:
        # Empty input/ and output/ scaffolding (driver<->harness jobs channels).
        (staging / "input" / "jobs").mkdir(parents=True, exist_ok=True)
        (staging / "output" / "jobs").mkdir(parents=True, exist_ok=True)

        # checkout/ — the repo the agent works in (workdir).
        checkout = staging / CHECKOUT_DIRNAME
        shutil.copytree(src, checkout, ignore=_SEED_IGNORE)
        _git_init_seed(checkout)

        # input/manifest.json — a production manifest (mode: run, round 1).
        manifest = api.Manifest(
            run_id=run_id,
            mode=api.MODE_RUN,
            adapter="claude",
            workdir=CHECKOUT_DIRNAME,
            agent_timeout_seconds=float(budget_seconds),
            round=1,
            round_budget=0,
            schema_version=api.SCHEMA_VERSION,
        )
        api.write_manifest(staging, manifest)

        # input/prompt.md — the production implementer prompt, byte-for-byte.
        issue = _synthetic_issue(benchmark, mode)
        api.atomic_write(
            staging / api.PROMPT_FILE, api.render_run_prompt(issue, 1, None)
        )

        # input/issue.json + input/issue/ Context Tree.
        _write_issue_metadata(staging, issue)
        api.write_tree(
            staging / "input",
            api.ContextSnapshot(issue=issue, issue_comments=[], timeline=[]),
        )

        os.replace(staging, job)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return job
