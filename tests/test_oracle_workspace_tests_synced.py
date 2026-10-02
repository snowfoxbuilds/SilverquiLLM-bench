"""Oracle audited suites and skills mirror their authoritative benchmark copies."""

from pathlib import Path

import pytest

from scripts.oracle_support import load_layout

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ("sos", "hob-medium", "fra-hard")


def layout(benchmark):
    return load_layout(ROOT, benchmark)


def oracle_pairs():
    for benchmark in BENCHMARKS:
        oracle = layout(benchmark).oracle / "tests/audited"
        for path in sorted(oracle.rglob("tests.py")):
            yield pytest.param(
                benchmark, path.relative_to(oracle), id=f"{benchmark}/{path.relative_to(oracle)}"
            )


@pytest.mark.parametrize("benchmark", BENCHMARKS)
def test_oracle_audited_tree_is_nonempty(benchmark):
    assert list((layout(benchmark).oracle / "tests/audited").rglob("tests.py"))


@pytest.mark.parametrize("benchmark,relative", list(oracle_pairs()))
def test_oracle_audited_test_matches_canonical(benchmark, relative):
    selected = layout(benchmark)
    canonical = selected.benchmark_root / "data/tests/audited" / relative
    oracle = selected.oracle / "tests/audited" / relative
    assert canonical.is_file(), f"Missing authoritative suite: {canonical}"
    assert oracle.read_bytes() == canonical.read_bytes(), f"Audited copy drift: {oracle}"


@pytest.mark.parametrize("benchmark", ("hob-medium", "fra-hard"))
def test_v2_oracle_mirrors_every_authoritative_suite(benchmark):
    selected = layout(benchmark)
    canonical = selected.benchmark_root / "data/tests/audited"
    for path in canonical.rglob("tests.py"):
        assert (selected.oracle / "tests/audited" / path.relative_to(canonical)).is_file()


@pytest.mark.parametrize("benchmark", BENCHMARKS)
def test_oracle_guidance_and_skills_match_canonical(benchmark):
    selected = layout(benchmark)
    assert (selected.workspace / "AGENTS.md").read_bytes() == (
        selected.oracle / "AGENTS.md"
    ).read_bytes()
    files = [p for p in (selected.workspace / "skills").rglob("*") if p.is_file()]
    assert files, f"Missing canonical skills: {selected.workspace}"
    for path in files:
        relative = path.relative_to(selected.workspace)
        assert path.read_bytes() == (selected.oracle / relative).read_bytes(), str(relative)
