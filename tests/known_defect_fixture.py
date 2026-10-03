"""A minimal benchmark built the Known-Best way, with one engine and one FDN Known Defect.

``kd`` targets one HOB card. Its Workspace carries a seeded engine defect (``lifegain``
loses one point) and an inherited FDN defect (``fdn_1``'s toughness), so the unmodified
Workspace passes 2 of the 4 regression Audited Tests; its Test Oracle Workspace fixes both
and implements the target. ``fdn_2`` has no Audited Tests, so the FDN population always
has a coverage gap, as on every real benchmark.
"""

from __future__ import annotations

import json
from pathlib import Path

BENCHMARK = "kd"
PYTEST_INI = "[pytest]\npython_files = test_*.py tests.py\naddopts = --import-mode=importlib\n"
ENGINE_NODES = ("test_rules.py::test_damage", "test_rules.py::test_lifegain")
FDN_NODES = ("fdn_1/tests.py::test_power", "fdn_1/tests.py::test_toughness")
ENGINE_DEFECT = "test_rules.py::test_lifegain"
FDN_DEFECT = "fdn_1/tests.py::test_toughness"

RULES = "def damage(amount):\n    return amount\n\n\ndef lifegain(amount):\n    return amount{}\n"
CARD = "POWER = {}\nTOUGHNESS = {}\n"
TARGET_STUB = "def effect():\n    raise NotImplementedError\n"
TARGET = "def effect():\n    return 'done'\n"

MANIFEST = {
    "schema_version": 1,
    "benchmark": BENCHMARK,
    "defects": [
        {
            "id": "lifegain-loses-one",
            "description": "Gaining life gains one less than the amount.",
            "rules": ["CR 119.3"],
            "kind": "seeded",
            "failing_tests": {"engine_regression": [ENGINE_DEFECT]},
        },
        {
            "id": "fdn-1-toughness",
            "description": "fdn_1 has toughness 1 instead of 2.",
            "rules": ["CR 208.1"],
            "kind": "inherited",
            "failing_tests": {"fdn_regression": [FDN_DEFECT]},
        },
    ],
}


def write_tree(root: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def workspace_files(*, fixed: bool) -> dict[str, str]:
    return {
        "engine/__init__.py": "",
        "engine/card.py": "value = 1\n",
        "engine/game_state.py": "",
        "engine/types.py": "",
        "engine/rules.py": RULES.format("" if fixed else " - 1"),
        "cards/__init__.py": "",
        "cards/fdn/__init__.py": "",
        "cards/fdn/fdn_1/__init__.py": "",
        "cards/fdn/fdn_1/card_impl.py": CARD.format(2, 2 if fixed else 1),
        "cards/fdn/fdn_1/card_spec.json": '{"collector_number":"1","name":"Example"}',
        "cards/fdn/fdn_2/__init__.py": "",
        "cards/fdn/fdn_2/card_impl.py": "",
        "cards/fdn/fdn_2/card_spec.json": '{"collector_number":"2","name":"Uncovered"}',
        "cards/hob/__init__.py": "",
        "cards/hob/hob_1/__init__.py": "",
        "cards/hob/hob_1/card_impl.py": TARGET if fixed else TARGET_STUB,
        "cards/hob/hob_1/card_spec.json": '{"collector_number":"1","name":"Target"}',
        "test_utils.py": "",
        "conftest.py": "",
        "pytest.ini": PYTEST_INI,
        # The Engine Reference Tests encode the defect; they are never graded.
        "engine_tests/test_rules.py": "from engine.rules import lifegain\n\n\n"
        "def test_lifegain():\n    assert lifegain(3) == 2\n",
    }


def build(bench_root: Path, *, manifest: bool = True) -> Path:
    """Write ``benchmarks/kd`` under ``bench_root`` and return ``bench_root``."""
    root = bench_root / "benchmarks" / BENCHMARK
    (root).mkdir(parents=True)
    (root / "config.json").write_text(
        json.dumps({"id": BENCHMARK, "cards": ["1"], "draft_set": {"primary_set_code": "HOB"}})
    )
    write_tree(root / "workspace", workspace_files(fixed=False))
    write_tree(root / "data/test_oracle_workspace", workspace_files(fixed=True))
    write_tree(
        root / "data/tests/audited",
        {
            "engine/test_rules.py": "from engine.rules import damage, lifegain\n\n\n"
            "def test_damage():\n    assert damage(3) == 3\n\n\n"
            "def test_lifegain():\n    assert lifegain(3) == 3\n",
            "fdn/fdn_1/tests.py": "from card_impl import POWER, TOUGHNESS\n\n\n"
            "def test_power():\n    assert POWER == 2\n\n\n"
            "def test_toughness():\n    assert TOUGHNESS == 2\n",
            "hob/hob_1/tests.py": "from card_impl import effect\n\n\n"
            "def test_effect():\n    assert effect() == 'done'\n",
        },
    )
    if manifest:
        write_manifest(root, MANIFEST)
    return bench_root


def write_manifest(root: Path, value) -> None:
    (root / "data/known_defects.json").write_text(json.dumps(value, indent=2))


def candidate_edits(workspace: Path) -> None:
    """Fix the engine defect, break fdn_1's power, and implement the target."""
    (workspace / "engine/rules.py").write_text(RULES.format(""))
    (workspace / "cards/fdn/fdn_1/card_impl.py").write_text(CARD.format(3, 1))
    (workspace / "cards/hob/hob_1/card_impl.py").write_text(TARGET)
