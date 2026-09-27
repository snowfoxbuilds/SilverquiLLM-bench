"""Grading entry point that runs only inside the grader container (ADR-013).

It lives outside ``silverquillm.karn`` because importing that package needs
host-only dependencies the grader image does not carry. The host mounts
SilverquiLLM at the package root and the read-only grading inputs under the
grade root; ``job.json`` names what to grade. Nothing is mounted writable: the
result leaves as one sentinel-framed line on the original stdout, and every other
write to stdout during grading is discarded so it cannot corrupt that line.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from silverquillm.evaluator import evaluate, evaluate_run


@dataclass(frozen=True)
class _Benchmark:
    root: Path
    target_set: str
    cards: list[str]


def _copy_regular_tree(source: Path, destination: Path) -> None:
    """Copy a read-only legacy run input into writable scratch, dropping links."""
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            continue
        target = destination / path.relative_to(source)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)


def grade(package_root: Path, grade_root: Path) -> dict:
    job = json.loads((grade_root / "job.json").read_text())
    if job["kind"] == "karn":
        benchmark = _Benchmark(
            package_root / "benchmarks" / job["benchmark"], job["target_set"], list(job["cards"])
        )
        result = evaluate_run(
            grade_root / "run",
            benchmark,
            timeout=job["timeout"],
            workspace_source=grade_root / "workspace",
        )
    elif job["kind"] == "legacy":
        # Legacy evaluation writes per-card results beside the run's inputs.
        run = Path(tempfile.mkdtemp(prefix="legacy-run-"))
        if (grade_root / "run").is_dir():
            _copy_regular_tree(grade_root / "run", run)
        legacy = grade_root / "legacy" / "workspace"
        result = evaluate(run, legacy / "cards", legacy / "engine", timeout=job["timeout"])
    else:
        raise ValueError("unknown grading job")
    return asdict(result)


EVALUATION_SENTINEL = b"SILVERQUILLM-EVALUATION-V1 "


def main(package_root: str, grade_root: str) -> int:
    # os.dup is non-inheritable, so pytest subprocesses never receive the result stream.
    result = os.dup(1)
    quiet = os.open(os.devnull, os.O_WRONLY)
    os.dup2(quiet, 1)
    os.close(quiet)
    sys.stdout = open(1, "w", closefd=False)  # noqa: SIM115 -- fd 1 is now /dev/null.
    evaluation = grade(Path(package_root), Path(grade_root))
    document = EVALUATION_SENTINEL + json.dumps(evaluation, sort_keys=True).encode() + b"\n"
    with os.fdopen(result, "wb") as stream:
        stream.write(document)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
