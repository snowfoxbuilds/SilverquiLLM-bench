"""Where a run came from, and the clean-source rule a run must meet before it launches.

A record from any host must be traceable to committed sources: the candidate recipe the
image was built from (Karn's ``karn.config.revision`` image label) and the bench code and
benchmark data that ran and graded it. A dirty source is refused unless the operator
passes ``--allow-dirty``, and the record keeps what was overridden.

The grader mounts the imported ``silverquillm`` package, so a run or regrade is refused
outright when that package is not the bench root's own: ``--allow-dirty`` cannot override
grading with another checkout's code.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
from pathlib import Path

from .definition import KarnError

HOST_LABEL_ENV = "SILVERQUILLM_HOST_LABEL"
RECIPE_LABEL = "karn.config.revision"
PACKAGE = Path(__file__).resolve().parents[1]
# Untracked files here change what runs or grades; untracked files elsewhere (scratch
# notes, worktrees, run artifacts) do not make a checkout dirty.
GUARDED_UNTRACKED = ("silverquillm", "benchmarks")
COMMIT = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
FIELDS = {
    "host_label",
    "host_label_source",
    "bench",
    "benchmark_root",
    "recipe_revision",
    "allow_dirty",
    "dirty_reasons",
}


class DirtySourceError(KarnError):
    """The run's sources are not all committed; the message lists each reason."""


class PackageSourceError(KarnError):
    """The imported ``silverquillm`` package is not the bench root's own."""


def require_package_from(bench_root: Path) -> None:
    """Refuse unless the imported package, which the grader mounts, is ``<bench_root>/silverquillm``.

    An editable install or a symlinked environment from another checkout would otherwise
    grade with that checkout's code while the benchmark data comes from *bench_root*.
    """
    expected = (Path(bench_root) / "silverquillm").resolve()
    if PACKAGE.resolve() != expected:
        raise PackageSourceError(
            f"package_source_mismatch: silverquillm is imported from {PACKAGE.resolve()}, "
            f"but the bench root's package is {expected}. Install silverquillm from the bench "
            f"root (pip install -e {Path(bench_root).resolve()}) or run with "
            f"PYTHONPATH={Path(bench_root).resolve()}."
        )


def host_label() -> tuple[str, str]:
    configured = os.environ.get(HOST_LABEL_ENV)
    if configured is not None:
        if not LABEL.fullmatch(configured):
            raise KarnError("invalid_host_label")
        return configured, "env"
    name = socket.gethostname().split(".")[0]
    return (name if LABEL.fullmatch(name) else "unknown"), "hostname"


def _git(directory: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(directory), *arguments],
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"},
        capture_output=True,
        check=False,
        timeout=60,
    )


def checkout_state(directory: Path) -> dict:
    """The commit of the checkout holding *directory*, and whether it has uncommitted changes.

    Dirty means a change to any tracked file, staged or not, or an untracked file under
    ``silverquillm/`` or ``benchmarks/``. Ignored files never count.
    """
    top = _git(directory, "rev-parse", "--show-toplevel")
    head = _git(directory, "rev-parse", "HEAD")
    commit = head.stdout.decode().strip()
    if top.returncode or head.returncode or not COMMIT.fullmatch(commit):
        return {"commit": None, "dirty": None}
    root = top.stdout.decode().strip()
    tracked = _git(Path(root), "status", "--porcelain=v1", "-z", "--untracked-files=no")
    untracked = _git(
        Path(root),
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--",
        *GUARDED_UNTRACKED,
    )
    if tracked.returncode or untracked.returncode:
        return {"commit": commit, "dirty": None}
    return {"commit": commit, "dirty": bool(tracked.stdout.strip() or untracked.stdout.strip())}


def recipe_revision(image_labels: dict) -> str | None:
    value = (image_labels or {}).get(RECIPE_LABEL)
    return value if isinstance(value, str) else None


def collect(image_labels: dict, bench_root: Path, *, allow_dirty: bool) -> dict:
    """The run's provenance; raises :class:`DirtySourceError` unless every source is clean.

    ``bench`` is the checkout of the imported package, the code the grader mounts.
    """
    require_package_from(bench_root)
    label, source = host_label()
    bench = checkout_state(PACKAGE)
    benchmark_root = checkout_state(Path(bench_root).resolve())
    revision = recipe_revision(image_labels)
    reasons = []
    for name, state in (("bench_checkout", bench), ("benchmark_root", benchmark_root)):
        if state["commit"] is None:
            reasons.append(name + "_not_a_git_checkout")
        elif state["dirty"] is None:
            reasons.append(name + "_status_unavailable")
        elif state["dirty"]:
            reasons.append(name + "_dirty")
    if revision is None:
        reasons.append("recipe_revision_unrecorded")
    elif not COMMIT.fullmatch(revision):
        reasons.append("recipe_revision_dirty")
    if reasons and not allow_dirty:
        raise DirtySourceError("dirty_source_refused:" + ",".join(reasons))
    return {
        "host_label": label,
        "host_label_source": source,
        "bench": bench,
        "benchmark_root": benchmark_root,
        "recipe_revision": revision,
        "allow_dirty": allow_dirty,
        "dirty_reasons": reasons,
    }


def valid(value) -> bool:
    def state(item):
        return (
            isinstance(item, dict)
            and set(item) == {"commit", "dirty"}
            and (item["commit"] is None or bool(COMMIT.fullmatch(str(item["commit"]))))
            and item["dirty"] in (True, False, None)
        )

    return (
        isinstance(value, dict)
        and set(value) == FIELDS
        and isinstance(value["host_label"], str)
        and bool(LABEL.fullmatch(value["host_label"]))
        and value["host_label_source"] in ("env", "hostname")
        and state(value["bench"])
        and state(value["benchmark_root"])
        and (value["recipe_revision"] is None or isinstance(value["recipe_revision"], str))
        and type(value["allow_dirty"]) is bool
        and isinstance(value["dirty_reasons"], list)
        and all(isinstance(reason, str) for reason in value["dirty_reasons"])
        and (value["allow_dirty"] or not value["dirty_reasons"])
    )
