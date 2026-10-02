"""The mixed hard pool stays complete, reproducible, and hidden from candidates."""

import ast
import hashlib
import json
from pathlib import Path

import pytest

from scripts.oracle_support import check_v2_api, load_layout, readiness_errors

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks/fra-hard"
POOL = (
    ("fra", "1"), ("fra", "49"), ("fra", "64"), ("fra", "159"), ("fra", "179"),
    ("hob", "33"), ("hob", "76"), ("hob", "86"), ("hob", "167"), ("hob", "174"),
)


def test_pool_preserves_both_sets_and_pinned_card_definitions():
    config = json.loads((BENCH / "config.json").read_text())
    assert config["cards"] == [f"{code}:{number}" for code, number in POOL]
    assert config["draft_set"]["primary_set_code"] == "FRA"
    assert config["draft_set"]["extra_set_codes"] == ["HOB"]
    pool = json.loads((BENCH / "data/pool.json").read_text())
    assert [(card["set"], card["collector_number"]) for card in pool] == list(POOL)
    raw = {
        (code, card["collector_number"]): card
        for code in ("fra", "hob")
        for card in json.loads((ROOT / f"data/sets/{code}.json").read_text())
    }
    for card in pool:
        original = raw[card["set"], card["collector_number"]]
        for key in ("name", "oracle_text", "card_faces", "layout", "mana_cost", "type_line"):
            assert card.get(key) == original.get(key), (card["name"], key)


@pytest.mark.parametrize("code,number", POOL)
def test_target_has_only_a_stub_and_spec_in_candidate_workspace(code, number):
    relative = Path("cards") / code / f"{code}_{number}"
    candidate = BENCH / "workspace" / relative
    oracle = BENCH / "data/test_oracle_workspace" / relative
    tree = ast.parse((candidate / "card_impl.py").read_text())
    methods = [
        node.name for cls in tree.body if isinstance(cls, ast.ClassDef)
        for node in cls.body if isinstance(node, ast.FunctionDef)
    ]
    assert methods == ["__init__"]
    assert not (candidate / "instructions.md").exists()
    assert not (candidate / "tests.py").exists()
    assert (candidate / "card_spec.json").read_bytes() == (oracle / "card_spec.json").read_bytes()
    spec = json.loads((candidate / "card_spec.json").read_text())
    assert (spec["set"], spec["collector_number"]) == (code, number)
    if (code, number) in {("fra", "49"), ("hob", "174")}:
        assert len(spec["card_faces"]) == 2


def test_candidate_target_tree_contains_exactly_the_selected_pool():
    selected = {f"cards/{code}/{code}_{number}/card_impl.py" for code, number in POOL}
    actual = {
        str(path.relative_to(BENCH / "workspace"))
        for code in ("fra", "hob")
        for path in (BENCH / "workspace/cards" / code).glob("*/card_impl.py")
    }
    assert actual == selected


@pytest.mark.parametrize("relative", ("data/tests/audited", "data/test_oracle_workspace/tests/audited"))
def test_target_hidden_suites_cover_exactly_the_selected_pool(relative):
    selected = {f"{code}/{code}_{number}/tests.py" for code, number in POOL}
    root = BENCH / relative
    actual = {
        str(path.relative_to(root))
        for code in ("fra", "hob")
        for path in (root / code).rglob("tests.py")
    }
    assert actual == selected


def test_candidate_engine_preserves_baseline_and_excludes_oracle_material():
    workspace = BENCH / "workspace"
    provenance = json.loads((BENCH / "data/provenance.json").read_text())
    pinned = provenance["candidate_baseline_files"]
    assert pinned
    engine_files = {str(path.relative_to(workspace)) for path in (workspace / "engine").rglob("*.py")}
    assert engine_files == {path for path in pinned if path.startswith("engine/") and path.endswith(".py")}
    for relative, digest in pinned.items():
        assert hashlib.sha256((workspace / relative).read_bytes()).hexdigest() == digest, relative
    assert not (workspace / "data").exists()
    assert not (workspace / "tests/audited").exists()
    assert not (workspace / "test_oracle_workspace").exists()
    assert not any(path.is_symlink() for path in BENCH.rglob("*"))


@pytest.mark.parametrize("code,number", POOL)
def test_every_selected_oracle_and_portable_hidden_suite_is_ready(code, number):
    layout = load_layout(ROOT, "fra-hard", require_cards=True)
    card_id = f"{code}_{number}"
    assert not readiness_errors(layout, card_id)
    suite = layout.suite(card_id)
    assert not check_v2_api(suite, layout)
    relative = suite.relative_to(BENCH / "data/tests")
    assert suite.read_bytes() == (layout.oracle / "tests" / relative).read_bytes()


def test_hidden_helpers_use_the_candidate_public_api():
    layout = load_layout(ROOT, "fra-hard", require_cards=True)
    assert not check_v2_api(layout.oracle / "test_utils.py", layout, helper=True)
    provenance = json.loads((BENCH / "data/provenance.json").read_text())
    assert hashlib.sha256((layout.oracle / "test_utils.py").read_bytes()).hexdigest() == (
        provenance["test_helpers"]["sha256"]
    )
    assert (layout.oracle / "test_utils.md").read_bytes() == (
        BENCH / "workspace/test_utils.md"
    ).read_bytes()
