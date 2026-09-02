"""Job-directory staging: the bench's imitation of TheOzolith's job dir.

A Contract Run drives a candidate through the *same* on-disk seam the
production substrate uses (ADR-0013/0019/0046): a per-run job directory mounted
read-write beside the workspace, holding the task the agent reads, the Context
Tree it navigates, and the ``output/`` slot where it writes its Output Proposal.
Benchmark evidence transfers by construction because the contract is identical.

Substrate fidelity (see the PR's Decisions Section for deliberate deviations):

- Mount point ``/job``; job I/O under ``input/`` and ``output/``.
- ``input/manifest.json`` — serialized with ``sort_keys=True`` (deterministic).
- ``input/prompt.md`` — the full agent-facing task (``manifest.task_path``).
- ``input/issue.json`` + ``input/issue/`` — the Context Tree: the synthetic
  issue split into per-item files with per-surface index files, serialized
  deterministically, never relevance-filtered/summarized/truncated.
- ``output/`` — empty; the agent writes ``output/proposal.json`` there.

Determinism is a contract: :func:`stage_job_dir` is a pure function of its
inputs — no timestamps, no run ids in the staged tree — so staging the same
inputs twice yields a byte-identical tree.

Public API
----------
- :class:`BenchmarkRef` — a resolved, runnable benchmark.
- :func:`load_benchmark` — resolve ``benchmarks/<id>/config.json``.
- :func:`stage_job_dir` — build ``run_dir/job/`` for one Contract Run.
- :class:`BenchmarkNotRunnableError` / :class:`BenchmarkNotFoundError`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from silverquillm.modes import BenchmarkMode
from silverquillm.proposal import SCHEMA_VERSION

__all__ = [
    "CONTAINER_JOB_PATH",
    "BenchmarkNotFoundError",
    "BenchmarkNotRunnableError",
    "BenchmarkRef",
    "load_benchmark",
    "pointer_prompt",
    "stage_job_dir",
]

_REPO_ROOT = Path(__file__).resolve().parent.parent

#: Where the job directory is bind-mounted inside the container (substrate parity).
CONTAINER_JOB_PATH = "/job"


def pointer_prompt() -> str:
    """The constant, constant-size pointer the headless agent is launched with.

    Verbatim from the substrate harness (ADR-0019): the argv carries only this
    pointer, never task content — the full task rides ``input/prompt.md``.
    """
    path = f"{CONTAINER_JOB_PATH}/input/prompt.md"
    return (
        f"Work on the task specified in {path}. Read that file first — it is "
        "your complete assignment — then execute it exactly."
    )

_SAFE_SEGMENT_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*\Z")


class BenchmarkNotRunnableError(Exception):
    """A benchmark exists but cannot be run (e.g. an empty card pool)."""


class BenchmarkNotFoundError(BenchmarkNotRunnableError):
    """No benchmark with the requested id (message lists the available ones)."""


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
    return sorted(
        p.name for p in root.iterdir() if (p / "config.json").is_file()
    )


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
# Rendering
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


def _render_problem_statement(benchmark: BenchmarkRef) -> str:
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
    return "\n".join(lines)


def _render_task(
    benchmark: BenchmarkRef, mode: BenchmarkMode, issue_title: str, problem_statement: str
) -> str:
    text = mode.task_template.read_text(encoding="utf-8")
    replacements = {
        "{{ISSUE_TITLE}}": issue_title,
        "{{PROBLEM_STATEMENT}}": problem_statement,
        "{{TARGET_SET}}": benchmark.target_set,
        "{{DISPLAY_NAME}}": benchmark.display_name,
        "{{BENCHMARK_ID}}": benchmark.id,
    }
    for token, value in replacements.items():
        text = text.replace(token, value)
    return text


def _dumps(obj: Any) -> str:
    """Deterministic JSON: sorted keys, fixed indent, trailing newline."""
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _empty_surface(label: str) -> str:
    """An empty-but-present Context Tree index surface (substrate shape)."""
    return f"# {label} (0)\n\n(none)\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def stage_job_dir(
    run_dir: Path,
    workspace: Path,
    benchmark: BenchmarkRef,
    mode: BenchmarkMode,
    budget_seconds: int,
) -> Path:
    """Stage ``run_dir/job/`` for one Contract Run and return the job dir.

    Deterministic: a pure function of its inputs. The staged tree carries no
    timestamps and no run id, so staging the same inputs twice is byte-identical.
    """
    workspace = Path(workspace)
    if not workspace.is_dir():
        raise FileNotFoundError(f"workspace not staged at {workspace}")

    job = Path(run_dir) / "job"
    job_input = job / "input"

    issue_title = f"Implement the {benchmark.display_name} card pool"
    problem_statement = _render_problem_statement(benchmark)

    # input/manifest.json — bench manifest.  Substrate-aligned field names
    # (agent_timeout_seconds, adapter) plus the bench-only benchmark/mode the
    # substrate bakes into the image; schema_version stamps the proposal schema.
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode.name,
        "benchmark": benchmark.id,
        "adapter": "claude",
        "agent_timeout_seconds": budget_seconds,
        "task_path": "input/prompt.md",
    }
    _write(job_input / "manifest.json", _dumps(manifest))

    # input/prompt.md — the full rendered task the pointer prompt points at.
    _write(job_input / "prompt.md", _render_task(benchmark, mode, issue_title, problem_statement))

    # Context Tree: input/issue.json + input/issue/ (per-surface index files).
    issue = {
        "body": problem_statement,
        "labels": [],
        "number": 0,
        "round": 0,
        "title": issue_title,
    }
    _write(job_input / "issue.json", _dumps(issue))
    _write(job_input / "issue" / "body.md", problem_statement + "\n")
    _write(job_input / "issue" / "comments" / "INDEX.md", _empty_surface("Comments"))
    _write(job_input / "issue" / "timeline.md", _empty_surface("Timeline"))

    # output/ — empty; the agent writes output/proposal.json here.
    (job / "output").mkdir(parents=True, exist_ok=True)

    return job
