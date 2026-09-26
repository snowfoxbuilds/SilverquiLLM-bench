"""Grading entry point that runs only inside the grader container (ADR-013).

It lives outside ``silverquillm.karn`` because importing that package needs
host-only dependencies the grader image does not carry. The host mounts
SilverquiLLM at the package root and the grading inputs and one writable output
directory under the grade root; ``job.json`` names what to grade.
"""

from __future__ import annotations

import json
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


def main(package_root: str, grade_root: str) -> int:
    root = Path(grade_root)
    evaluation = grade(Path(package_root), root)
    (root / "out" / "evaluation.json").write_text(json.dumps(evaluation, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
