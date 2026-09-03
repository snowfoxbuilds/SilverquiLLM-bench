"""Job-directory staging: the bench replays TheOzolith's implementer Run Contract.

A Contract Run drives a candidate through the *same* on-disk seam the production
substrate uses (BENCH-CONTRACT.md; ADR-0013/0019/0046): a per-run job directory
bind-mounted at ``/job`` holding the manifest, the driver-rendered task, the
Context Tree, the checked-out repo the agent works in, and the ``output/`` slot
the in-image harness and the agent write.  Benchmark evidence transfers by
construction because the bench does not imitate the contract — it *consumes*
TheOzolith's published entry points (``theozolith_worker.api``), so nothing here
can drift from production as the templates evolve.

What :func:`stage_job_dir` materializes (all via the published API):

- ``input/manifest.json`` — a production :class:`~theozolith_worker.api.Manifest`
  (``mode: "run"``, ``round: 1``, stamped ``schema_version``, the production
  default ``workdir``, the Candidate Bundle's ``adapter`` verbatim) written
  with :func:`~theozolith_worker.api.write_manifest`.  The real
  ``read_manifest`` rejects unknown keys, so the Benchmark Mode never rides
  the manifest — it lives on the RunRecord and shapes only the task.
- ``input/prompt.md`` — the production implementer prompt, byte-for-byte from
  :func:`~theozolith_worker.api.render_run_prompt` (the task rides the synthetic
  issue body it wraps, never a bench-authored template).
- ``input/issue.json`` + ``input/issue/`` — the synthetic GitHub-style issue and
  its Context Tree, the latter via :func:`~theozolith_worker.api.write_tree`.
- ``input/jobs/`` + ``output/jobs/`` — the driver↔harness jobs channel the gate
  travels over; ``output/`` is otherwise empty (the harness writes
  ``status.json``/``transcript.txt``, the agent ``proposal.json``).
- ``checkout/`` — the benchmark workspace, git-initialized with a seed commit so
  the agent sees an ordinary repository (``git status``/``git diff``).

Beside the job dir — outside the bind mount, so nothing that runs in the
container can reach it — :func:`stage_job_dir` also creates the **driver-owned
repository** ``run_dir/driver.git`` (:func:`driver_git_dir`), seeded with the
same tree.  The driver's post-exit commit is made through that repository with
the checkout as its work tree (:func:`driver_git`), never through the
checkout's own ``.git``: hooks, ``core.fsmonitor``, filters, or aliases a
candidate plants in ``checkout/.git`` are candidate-controlled code and would
otherwise execute in the benchmark process at commit time.

Staging is atomic and retry-safe: the job tree is built in a private sibling
and published with a single :func:`os.replace` as the last step, and an
existing job dir or driver repository is a loud conflict — a retry can never
inherit a prior attempt's proposal, status, transcript, or checkout.

Public API
----------
- :class:`BenchmarkRef` — a resolved, runnable benchmark.
- :func:`load_benchmark` — resolve ``benchmarks/<id>/config.json``.
- :func:`stage_job_dir` — build ``run_dir/job/`` (+ ``run_dir/driver.git``).
- :func:`driver_git_dir` / :func:`driver_git` — the driver-owned repository.
- :class:`BenchmarkNotRunnableError` / :class:`BenchmarkNotFoundError`
  / :class:`JobDirConflictError`.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from theozolith_worker import api

from silverquillm.modes import BenchmarkMode

__all__ = [
    "CHECKOUT_DIRNAME",
    "CONTAINER_JOB_PATH",
    "DRIVER_GIT_DIRNAME",
    "JOB_DIRNAME",
    "BenchmarkNotFoundError",
    "BenchmarkNotRunnableError",
    "BenchmarkRef",
    "JobDirConflictError",
    "driver_git",
    "driver_git_dir",
    "load_benchmark",
    "stage_job_dir",
]

_REPO_ROOT = Path(__file__).resolve().parent.parent

#: Where the job directory is bind-mounted inside the container (substrate parity).
CONTAINER_JOB_PATH = api.CONTAINER_JOB_PATH  # "/job"

#: The job dir's name under a run dir.
JOB_DIRNAME = "job"

#: The driver-owned bare repository beside the job dir (never mounted).
DRIVER_GIT_DIRNAME = "driver.git"

#: The manifest's ``workdir`` — the agent's working directory under ``/job`` —
#: taken from the production manifest's own default, never restated.
CHECKOUT_DIRNAME: str = next(
    f.default for f in dataclasses.fields(api.Manifest) if f.name == "workdir"
)

_SEED_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".git")
_GIT_ID = ["-c", "user.name=silverquillm", "-c", "user.email=driver@silverquillm"]

_SAFE_SEGMENT_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*\Z")


class BenchmarkNotRunnableError(Exception):
    """A benchmark exists but cannot be run (e.g. an empty card pool)."""


class BenchmarkNotFoundError(BenchmarkNotRunnableError):
    """No benchmark with the requested id (message lists the available ones)."""


class JobDirConflictError(Exception):
    """A job dir (or driver repository) already exists where a fresh Contract
    Run would be staged."""


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


# ---------------------------------------------------------------------------
# Git: the agent-visible seed and the driver-owned repository
# ---------------------------------------------------------------------------


def driver_git_dir(run_dir: Path) -> Path:
    """The driver-owned bare repository for *run_dir* (outside the job mount)."""
    return Path(run_dir) / DRIVER_GIT_DIRNAME


def driver_git(
    run_dir: Path,
    checkout: Path,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run ``git`` against the driver-owned repository with *checkout* as its
    work tree.

    ``GIT_DIR`` names ``run_dir/driver.git`` explicitly, so git never discovers —
    and never reads hooks, config, or the index of — the ``.git`` inside the
    candidate-touched checkout.  Only the work tree's files are read.
    """
    env = {
        **os.environ,
        "GIT_DIR": str(driver_git_dir(run_dir)),
        "GIT_WORK_TREE": str(checkout),
    }
    return subprocess.run(
        ["git", *_GIT_ID, *args],
        cwd=checkout,
        env=env,
        capture_output=True,
        text=True,
        check=check,
    )


def _git_init_seed(checkout: Path) -> None:
    """The agent-visible repository inside the checkout (never trusted later)."""
    subprocess.run(["git", "init", "-q"], cwd=checkout, check=True)
    subprocess.run(["git", *_GIT_ID, "add", "-A"], cwd=checkout, check=True)
    subprocess.run(
        ["git", *_GIT_ID, "commit", "-q", "-m", "initial checkout"],
        cwd=checkout,
        check=True,
    )


def _init_driver_git(run_dir: Path, checkout: Path) -> None:
    """Create ``run_dir/driver.git`` and seed it with the checkout's tree."""
    subprocess.run(["git", "init", "-q", "--bare", str(driver_git_dir(run_dir))], check=True)
    driver_git(run_dir, checkout, "add", "-A")
    driver_git(run_dir, checkout, "commit", "-q", "-m", "initial checkout")


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------


def stage_job_dir(
    run_dir: Path,
    benchmark: BenchmarkRef,
    mode: BenchmarkMode,
    *,
    run_id: str,
    budget_seconds: int,
    adapter: str,
) -> Path:
    """Stage ``run_dir/job/`` for one Contract Run and return the job dir.

    Builds the entire tree — manifest, prompt, issue metadata, Context Tree, the
    jobs channel, the git-seeded ``checkout/``, and an empty ``output/`` — in a
    private sibling, seeds the driver-owned ``run_dir/driver.git`` from it, and
    publishes the job dir with a single atomic rename as the very last step.
    An existing ``run_dir/job`` or ``run_dir/driver.git`` is a loud
    :class:`JobDirConflictError`: a fresh or retried run never inherits a prior
    attempt's proposal, status, transcript, or checkout.

    *adapter* is the Candidate Bundle's adapter name, stamped into the
    production manifest verbatim — the in-image harness invokes that adapter.
    It is an opaque field here: the bench keeps no adapter allowlist
    (BENCH-CONTRACT.md — the format never hardcodes the adapter set).
    """
    if not isinstance(adapter, str) or not adapter:
        raise ValueError("stage_job_dir requires the candidate's adapter name")
    run_dir = Path(run_dir)
    job = run_dir / JOB_DIRNAME
    driver_repo = driver_git_dir(run_dir)
    for existing in (job, driver_repo):
        if existing.exists():
            raise JobDirConflictError(
                f"{existing} already exists; a Contract Run never overwrites another "
                "attempt's job directory (stage into a fresh run dir)"
            )
    src = benchmark.root / "workspace"
    if not src.is_dir() or not any(src.iterdir()):
        raise FileNotFoundError(f"benchmark workspace missing or empty: {src}")

    run_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=run_dir, prefix=".job-staging-"))
    try:
        # The driver<->harness jobs channel, empty; output/ otherwise empty.
        (staging / "input" / "jobs").mkdir(parents=True, exist_ok=True)
        (staging / "output" / "jobs").mkdir(parents=True, exist_ok=True)

        # checkout/ — the repo the agent works in (the manifest's workdir).
        checkout = staging / CHECKOUT_DIRNAME
        shutil.copytree(src, checkout, ignore=_SEED_IGNORE)
        _git_init_seed(checkout)

        # input/manifest.json — a production manifest (mode: run, round 1).
        manifest = api.Manifest(
            run_id=run_id,
            mode=api.MODE_RUN,
            adapter=adapter,
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

        # The driver-owned repository, seeded from the same tree; then publish.
        _init_driver_git(run_dir, checkout)
        os.replace(staging, job)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(driver_repo, ignore_errors=True)
        raise
    return job
