"""Build candidate assets from pinned raw sets; seed the oracle only once.

Run ``python3 scripts/build_fra_hard.py`` from any directory. Existing oracle
implementations and hidden tests are never overwritten.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "benchmarks/fra-hard"
BASE = ROOT / "benchmarks/hob-medium"
TARGETS = {"fra": (1, 49, 64, 159, 179), "hob": (33, 76, 86, 167, 174)}
RULEBOOK_URL = "https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt"
FIELDS = ("name", "mana_cost", "type_line", "oracle_text", "colors", "keywords",
          "rarity", "set", "collector_number", "power", "toughness", "loyalty",
          "layout", "card_faces")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def copy_new(source: Path, destination: Path) -> None:
    if destination.exists():
        return
    if source.is_dir():
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns(
            "__pycache__", ".pytest_cache", "*.pyc"))
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def stage_test_helpers(workspace: Path, oracle: Path) -> None:
    source = (BASE / "workspace/test_utils.py").read_text()
    old = '''    """Resolve the entire stack (public alias for the internal resolver)."""
    _resolve_top_of_stack(game)'''
    new = '''    """Settle a priority boundary, including state-based actions on an empty stack."""
    from engine.state_based_actions import resolve_state_based_actions

    resolve_state_based_actions(game)
    _resolve_top_of_stack(game)'''
    if source.count(old) != 1:
        raise ValueError("Baseline resolve_stack helper changed; review the FRA adaptation")
    source = source.replace(old, new)
    documentation = (BASE / "workspace/test_utils.md").read_text().replace(
        "`resolve_stack(game) -> None` — resolve the entire stack.",
        "`resolve_stack(game) -> None` — check state-based actions first (even when "
        "the stack is empty), then resolve the entire stack.",
    )
    for destination in (workspace, oracle):
        (destination / "test_utils.py").write_text(source)
        (destination / "test_utils.md").write_text(documentation)


def stub(spec: dict) -> str:
    face = spec.get("card_faces", [spec])[0]
    name = face["name"]
    classname = re.sub(r"[^a-zA-Z0-9 ]", "", name).replace(" ", "")
    types, _, subtypes = face["type_line"].partition(" — ")
    base = next(t for t in ("Creature", "Artifact", "Enchantment", "Instant", "Sorcery", "Land") if t in types)
    values = {"name": repr(name), "mana_cost": f'ManaCost.parse({face.get("mana_cost", "")!r})',
              "rules_text": repr(face.get("oracle_text", ""))}
    if base == "Creature":
        values.update(base_power=repr(int(face["power"])), base_toughness=repr(int(face["toughness"])))
    if subtypes:
        values["subtypes"] = "{" + ", ".join(repr(s) for s in subtypes.split()) + "}"
    if "Legendary" in types:
        values["supertypes"] = "{Supertype.LEGENDARY}"
    defaults = "\n".join(f"            {key!r}: {value}," for key, value in values.items())
    return (f"from engine.card import {base}\nfrom engine.types import ManaCost, Supertype\n\n\n"
            f"class {classname}({base}):\n"
            '    """Implementation task: see card_spec.json."""\n\n'
            "    def __init__(self, **kwargs):\n        defaults = {\n"
            f"{defaults}\n        }}\n        defaults.update(kwargs)\n        super().__init__(**defaults)\n")


def main() -> None:
    workspace = DEST / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    if not (workspace / "RULEBOOK.txt").exists():
        with urlopen(RULEBOOK_URL, timeout=30) as response:
            rules = response.read()
        if b"September 25, 2026" not in rules:
            raise ValueError("Unexpected Comprehensive Rules edition")
        (workspace / "RULEBOOK.txt").write_bytes(rules)
    for item in ("engine", "engine_tests", "skills", "conftest.py", "pytest.ini", "test_utils.py", "test_utils.md", ".gitignore"):
        copy_new(BASE / "workspace" / item, workspace / item)
    copy_new(BASE / "workspace/cards/fdn", workspace / "cards/fdn")
    for name in ("__init__.py", "loader.py", "registry.py"):
        copy_new(BASE / f"workspace/cards/{name}", workspace / f"cards/{name}")
    pool = []
    for code, numbers in TARGETS.items():
        raw = json.loads((ROOT / f"data/sets/{code}.json").read_text())
        for number in numbers:
            card, = [c for c in raw if c["collector_number"] == str(number)]
            spec = {key: card[key] for key in FIELDS if key in card}
            spec["mana_cost_str"] = card.get("mana_cost", card.get("card_faces", [{}])[0].get("mana_cost", ""))
            pool.append(spec)
            folder = workspace / f"cards/{code}/{code}_{number}"
            folder.mkdir(parents=True, exist_ok=True)
            (folder.parent / "__init__.py").touch()
            (folder / "__init__.py").touch()
            write_json(folder / "card_spec.json", spec)
            (folder / "card_impl.py").write_text(stub(spec))
    write_json(DEST / "data/pool.json", pool)
    config_path = DEST / "config.json"
    existing_config = json.loads(config_path.read_text()) if config_path.exists() else {}
    write_json(config_path, {
        "schema_version": 1, "id": "fra-hard", "display_name": "Reality Fracture + The Hobbit — Hard",
        "draft_set": {"primary_set_code": "FRA", "collector_range": "001-290", "extra_set_codes": ["HOB"]},
        "tier": existing_config.get("tier", "Beta"), "cards": [f"{s}:{n}" for s, ns in TARGETS.items() for n in ns],
        "leaderboard": {"requires_full_set": True, "requires_unfiltered": True}})
    (workspace / "instructions.md").write_text(
        "# FRA hard implementation task\n\nImplement the ten selected cards listed in the card specs under cards/fra/ and cards/hob/. "
        "Keep each class in its assigned card_impl.py with its provided name. card_spec.json contains the complete "
        "card specification, including card_faces for cards with multiple components. Implement the whole card.\n\n"
        "You may change engine/ freely. Use the Player Query / Player Decision protocol for choices. "
        "Your tests belong beside target implementations. Existing engine and FDN tests are read-only. "
        "Run `python3 -m pytest` from the workspace root. Consult RULEBOOK.txt for rules and test_utils.md for test APIs.\n")
    orientation = (BASE / "workspace/AGENTS.md").read_text()
    orientation = orientation.replace(" and each target card's `instructions.md`", " and each target card's `card_spec.json`")
    orientation = orientation.replace("HOB", "FRA and HOB").replace("cards/hob/{card_id}", "cards/{set_code}/{card_id}")
    orientation = orientation.replace("`cards/hob/`", "`cards/fra/` and `cards/hob/`")
    orientation = orientation.replace("cards/hob/hob_<N>/tests.py", "cards/{set_code}/{set_code}_<N>/tests.py")
    orientation = orientation.replace("cards/hob/hob_{collector_number}/tests.py", "cards/{set_code}/{set_code}_{collector_number}/tests.py")
    orientation = orientation.replace("from cards.hob.hob_<N>.card_impl import <ClassName>",
                                      "from cards.fra.fra_<N>.card_impl import <ClassName>\nfrom cards.hob.hob_<N>.card_impl import <ClassName>")
    (workspace / "AGENTS.md").write_text(orientation)
    (workspace / "PROJECT_MAP.md").write_text(
        "# Workspace layout\n\nengine/ contains the editable game engine; cards/fdn/ contains reference cards. "
        "engine_tests/ and existing cards/fdn/*/tests.py are regression tests.\n\n"
        "The ten targets live in cards/fra/fra_<N>/ and cards/hob/hob_<N>/. Each has card_spec.json and "
        "card_impl.py; add your tests.py there. Specs with card_faces describe every component of one target card.\n\n"
        "instructions.md and AGENTS.md describe the task. test_utils.py and test_utils.md provide test helpers. "
        "RULEBOOK.txt contains the Comprehensive Rules; skills/grep-rulebook explains rules lookup.\n")
    oracle = DEST / "data/test_oracle_workspace"
    copy_new(workspace, oracle)
    for name in ("loader.py", "registry.py"):
        copy_new(workspace / f"cards/{name}", oracle / f"cards/{name}")
    stage_test_helpers(workspace, oracle)
    copy_new(BASE / "data/tests/audited/fdn", DEST / "data/tests/audited/fdn")
    copy_new(DEST / "data/tests/audited/fdn", oracle / "tests/audited/fdn")
    for name in ("fdn_regression_coverage.json", "fdn_audit_migration.json"):
        if (BASE / "data" / name).exists():
            copy_new(BASE / "data" / name, DEST / "data" / name)
    manifest = {
        str(path.relative_to(workspace)): hashlib.sha256(path.read_bytes()).hexdigest()
        for directory in ("engine", "engine_tests", "cards/fdn")
        for path in sorted((workspace / directory).rglob("*"))
        if path.is_file() and not any(part in ("__pycache__", ".pytest_cache") for part in path.parts)
        and path.suffix != ".pyc"
    }
    for name in ("__init__.py", "loader.py", "registry.py"):
        path = workspace / f"cards/{name}"
        manifest[f"cards/{name}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(DEST / "data/provenance.json", {
        "candidate_baseline": "benchmarks/hob-medium/workspace",
        "candidate_baseline_files": manifest,
        "test_helpers": {
            "derived_from": "benchmarks/hob-medium/workspace/test_utils.py",
            "adaptation": "resolve_stack checks state-based actions before resolving the stack",
            "sha256": hashlib.sha256((workspace / "test_utils.py").read_bytes()).hexdigest(),
        },
        "rules": {"source": RULEBOOK_URL, "effective_date": "2026-09-25",
                  "sha256": hashlib.sha256((workspace / "RULEBOOK.txt").read_bytes()).hexdigest()},
        "raw_sets": {code: {"path": f"data/sets/{code}.json",
                            "sha256": hashlib.sha256((ROOT / f"data/sets/{code}.json").read_bytes()).hexdigest()}
                     for code in TARGETS},
    })
    print(f"Generated {len(pool)} target specs and candidate stubs in {workspace}")


if __name__ == "__main__":
    main()
