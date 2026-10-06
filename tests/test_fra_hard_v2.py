"""fra-hard-v2 stays complete, reproducible, and hidden from candidates (FRA-HARD-BENCHMARK.md)."""

import ast
import json
from pathlib import Path

import pytest

from scripts.oracle_support import check_v2_api, load_layout, readiness_errors
from silverquillm.karn.benchmark import Benchmark, load_benchmark

from .known_defect_checks import oracle_problems

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks/fra-hard-v2"
POOL = (
    ("fra", "1"), ("fra", "49"), ("fra", "64"), ("fra", "159"), ("fra", "179"),
    ("hob", "33"), ("hob", "76"), ("hob", "86"), ("hob", "174"),
    ("war", "143"), ("fut", "78"),
)
# The HOB targets' oracle implementations and suites are not ported yet (#157).
PORTED_TARGETS = tuple((code, number) for code, number in POOL if code == "fra")


def test_pool_keeps_each_targets_set():
    config = json.loads((BENCH / "config.json").read_text())
    assert config["id"] == "fra-hard-v2"
    assert config["cards"] == [f"{code}:{number}" for code, number in POOL]
    assert config["draft_set"] == {"primary_set_code": "FRA", "collector_range": "001-290",
                                   "extra_set_codes": ["HOB", "WAR", "FUT"]}
    assert config["tier"] == "Beta"
    pool = json.loads((BENCH / "data/pool.json").read_text())
    assert [(entry["set"], entry["collector_number"]) for entry in pool] == list(POOL)
    for entry in pool:
        spec = json.loads((BENCH / "workspace/cards" / entry["set"] / f"{entry['set']}_{entry['collector_number']}"
                           / "card_spec.json").read_text())
        assert (spec["name"], spec["oracle_text" if "oracle_text" in spec else "name"]) == (
            entry["name"], entry["oracle_text" if "oracle_text" in entry else "name"])


def _methods(tree: ast.Module) -> dict[str, list[str]]:
    return {
        cls.name: [node.name for node in cls.body if isinstance(node, ast.FunctionDef)]
        for cls in tree.body if isinstance(cls, ast.ClassDef)
    }


@pytest.mark.parametrize("code,number", POOL)
def test_target_is_a_behavior_free_stub_with_its_predefined_classes(code, number):
    relative = Path("cards") / code / f"{code}_{number}"
    candidate = BENCH / "workspace" / relative
    oracle = BENCH / "data/test_oracle_workspace" / relative
    spec = json.loads((candidate / "card_spec.json").read_text())
    assert (spec["set"], spec["collector_number"]) == (code, number)
    assert (candidate / "card_spec.json").read_bytes() == (oracle / "card_spec.json").read_bytes()
    assert sorted(path.name for path in candidate.iterdir() if path.name != "__pycache__") == [
        "__init__.py", "card_impl.py", "card_spec.json",
    ]
    methods = _methods(ast.parse((candidate / "card_impl.py").read_text()))
    faces = [name for name, body in methods.items() if body]
    assert all(body == ["__init__"] for body in methods.values() if body)
    assert len(faces) == len(spec.get("card_faces") or [spec])
    assert any(name.endswith("Ability1") for name in methods)


def test_fra_tokens_are_predefined_identically_for_candidate_and_oracle():
    candidate = BENCH / "workspace/cards/fra/tokens.py"
    assert candidate.read_bytes() == (BENCH / "data/test_oracle_workspace/cards/fra/tokens.py").read_bytes()
    assert all(body in ([], ["__init__"]) for body in _methods(ast.parse(candidate.read_text())).values())


@pytest.mark.parametrize("code,number", PORTED_TARGETS)
def test_ported_oracle_and_hidden_suite_are_ready_and_use_the_public_api(code, number):
    layout = load_layout(ROOT, "fra-hard-v2", require_cards=True)
    card_id = f"{code}_{number}"
    assert not readiness_errors(layout, card_id)
    suite = layout.suite(card_id)
    assert not check_v2_api(suite, layout)
    relative = suite.relative_to(BENCH / "data/tests")
    assert suite.read_bytes() == (layout.oracle / "tests" / relative).read_bytes()


def test_hidden_helpers_and_docs_match_the_candidate_copies():
    workspace, oracle = BENCH / "workspace", BENCH / "data/test_oracle_workspace"
    for name in ("test_utils.py", "test_utils.md", "instructions.md", "AGENTS.md"):
        assert (workspace / name).read_bytes() == (oracle / name).read_bytes(), name
    assert not (workspace / "data").exists()
    assert not (workspace / "tests").exists()
    assert not any(path.is_symlink() for path in BENCH.rglob("*"))


def test_candidate_engine_excludes_oracle_extensions():
    workspace = {p.name for p in (BENCH / "workspace/engine").glob("*.py")}
    oracle = {p.name for p in (BENCH / "data/test_oracle_workspace/engine").glob("*.py")}
    assert {"copying.py", "mana_grants.py", "planeswalker.py", "preparation.py", "ward.py"} <= oracle - workspace


def test_oracle_passes_every_ported_target_audited_test():
    benchmark = load_benchmark(ROOT, "fra-hard-v2")
    ported = {f"{code}:{number}" for code, number in PORTED_TARGETS}
    config = {**benchmark.config, "cards": [card for card in benchmark.cards if card in ported]}
    problems = oracle_problems(Benchmark(benchmark.id, benchmark.root, config), "card_correctness")
    assert problems == [], "\n".join(problems)


@pytest.mark.parametrize("code,number", PORTED_TARGETS)
def test_unimplemented_target_fails_its_hidden_suite(code, number):
    """The stubbed Workspace passes none of a target's behavior."""
    benchmark = load_benchmark(ROOT, "fra-hard-v2")
    config = {**benchmark.config, "cards": [f"{code}:{number}"]}
    from .known_defect_checks import audited_outcomes

    outcomes = audited_outcomes(Benchmark(benchmark.id, benchmark.root, config), BENCH / "workspace", "card_correctness")
    failed = [node for node, outcome in outcomes.nodes.items() if outcome == "fail"]
    assert len(failed) >= len(outcomes.nodes) // 2, outcomes.nodes
