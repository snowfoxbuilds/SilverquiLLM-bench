"""Fingerprints of host-owned grading inputs, kept separate from eligibility."""

from __future__ import annotations

from silverquillm.benchmark_targets import target_cards
from silverquillm.evaluator import _target_card_id, resolve_eval_paths

from .definition import KarnError, canonical, digest, read_regular, strict_json


def grading_inputs(benchmark) -> dict:
    paths = resolve_eval_paths(benchmark.root, benchmark.target_set)
    sources = []
    for card_set, number in target_cards(benchmark.target_set, benchmark.cards):
        audited_set = paths.audited_target.parent / card_set
        card = _target_card_id(card_set, number, audited_set)
        directory = audited_set / card
        sources.append(("target", directory / "tests.py"))
        if (directory / "conftest.py").exists():
            sources.append(("target", directory / "conftest.py"))
    if paths.audited_fdn.is_dir():
        for directory in sorted(paths.audited_fdn.iterdir()):
            if (directory / "tests.py").exists():
                sources.append(("fdn", directory / "tests.py"))
                if (directory / "conftest.py").exists():
                    sources.append(("fdn", directory / "conftest.py"))
    else:
        sources.append(("fdn", paths.audited_fdn))
    if paths.engine_tests.is_dir():
        for source in sorted(paths.engine_tests.rglob("*")):
            if (
                source.is_file()
                and "__pycache__" not in source.parts
                and not source.name.endswith(".pyc")
            ):
                sources.append(("engine", source))
    else:
        sources.append(("engine", paths.engine_tests))
    if paths.test_interface is not None:
        sources.append(("test_interface", paths.test_interface))
        sources.append(("table", paths.table))
    else:
        sources.append(("test_utils", paths.test_utils))
    for name in ("conftest.py", "pytest.ini"):
        source = paths.engine_support / name
        if source.is_file():
            sources.append(("engine_support", source))
    repository = benchmark.root.parent.parent
    golden = repository / "data/replays/golden"
    if golden.is_dir():
        for source in sorted(golden.rglob("*")):
            if source.is_file() and not {"__pycache__", ".pytest_cache", ".git"}.intersection(
                source.parts
            ):
                sources.append(("replay_fixture", source))
    triage = repository / "scripts/triage_divergences.py"
    if triage.is_file():
        sources.append(("replay_support", triage))
    sources.append(
        ("replay_token_map", benchmark.root.parent.parent / "data/replays/token_id_map.json")
    )
    sources.append(
        ("replay_card_map", benchmark.root.parent.parent / "data/replays/card_id_map.json")
    )
    coverage = benchmark.root / "data/fdn_regression_coverage.json"
    declared_coverage = None
    if coverage.exists():
        sources.append(("coverage", coverage))
        try:
            declared_coverage = strict_json(read_regular(coverage))
        except KarnError:
            declared_coverage = {"observation_error": "coverage_metadata_unavailable"}
    files, problems = [], []
    for kind, source in sources:
        try:
            relative = str(source.relative_to(benchmark.root.parent.parent))
        except ValueError:
            relative = str(source)
        item = {"kind": kind, "path": relative, "sha256": None}
        try:
            item["sha256"] = digest(read_regular(source, limit=32 * 1024 * 1024))
        except KarnError:
            problems.append({"kind": kind, "path": relative, "reason": "grading_input_unavailable"})
        files.append(item)
    result = {"files": files, "digest": digest(canonical(files)), "problems": problems}
    if declared_coverage is not None:
        result["declared_coverage"] = declared_coverage
    return result
