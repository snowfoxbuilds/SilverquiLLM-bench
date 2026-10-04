"""The printed-class generator (DECISION-MODEL.md › Printed identity)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FDN = REPO / "known_best/workspace/cards/fdn"
_SPEC = importlib.util.spec_from_file_location(
    "generate_printed_classes", REPO / "scripts/generate_printed_classes.py"
)
gen = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gen)

GLAMDRING = {
    "name": "Glamdring, Foe-hammer // Gleam of Death",
    "keywords": ["Equip", "Mill"],
    "card_faces": [
        {
            "name": "Glamdring, Foe-hammer",
            "mana_cost": "{2}",
            "type_line": "Legendary Artifact — Equipment",
            "oracle_text": "Instant and sorcery spells you cast cost {X} less to cast, "
                           "where X is equipped creature's power.\nEquip {2}",
        },
        {
            "name": "Gleam of Death",
            "mana_cost": "{3}{U}",
            "type_line": "Sorcery — Adventure",
            "oracle_text": "Mill six cards, then put all instant and sorcery cards from among "
                           "them into your hand. (Then exile this card. You may cast the "
                           "artifact later from exile.)",
        },
    ],
}


@pytest.mark.parametrize(("printed", "expected"), [
    ("Gleam of Death", "GleamOfDeath"),
    ("Glamdring, Foe-hammer", "GlamdringFoehammer"),
    ("Healer's Hawk", "HealersHawk"),
])
def test_class_name(printed, expected):
    assert gen.class_name(printed) == expected


def test_keywords_sharing_a_line_are_separate_abilities():
    assert gen.printed_abilities(
        "When you cast this spell, untap all lands you control.\nFlying, trample\n"
        "Ward—Sacrifice three permanents.", ["Flying", "Trample", "Ward"],
    ) == [
        "When you cast this spell, untap all lands you control.",
        "Flying",
        "trample",
        "Ward—Sacrifice three permanents.",
    ]
    assert gen.printed_abilities("Trample, ward {4}", ["Trample", "Ward"]) == ["Trample", "ward {4}"]


def test_a_line_with_commas_but_not_only_keywords_stays_one_ability():
    assert gen.printed_abilities("Enchant creature, land, or planeswalker", ["Enchant"]) == [
        "Enchant creature, land, or planeswalker"
    ]


def test_reminder_text_stays_with_its_ability():
    assert gen.printed_abilities(
        "Flash (You may cast this spell any time you could cast an instant.)\nFlying", ["Flash"]
    ) == ["Flash (You may cast this spell any time you could cast an instant.)", "Flying"]


def test_modes_are_numbered_in_printed_order():
    assert gen.printed_abilities(
        "Choose one —\n• Creatures you control get +2/+0 until end of turn.\n"
        "• Create two 1/1 red Goblin creature tokens."
    ) == [
        "Choose one —",
        "• Creatures you control get +2/+0 until end of turn.",
        "• Create two 1/1 red Goblin creature tokens.",
    ]


def _card_dir(tmp_path: Path, spec: dict) -> Path:
    card_dir = tmp_path / "card"
    card_dir.mkdir()
    (card_dir / "card_spec.json").write_text(json.dumps(spec))
    return card_dir


def test_a_two_face_stub_has_one_class_per_face_and_ability(tmp_path):
    card_dir = _card_dir(tmp_path, GLAMDRING)
    assert gen.generate(card_dir, make_stub=True)
    source = (card_dir / "card_impl.py").read_text()
    compile(source, "card_impl.py", "exec")
    declarations = [line for line in source.splitlines() if line.startswith(("class ", "    text = "))]
    assert declarations == [
        "class GlamdringFoehammerAbility1:",
        ("    text = \"Instant and sorcery spells you cast cost {X} less to cast, "
         "where X is equipped creature's power.\""),
        "class GlamdringFoehammerAbility2:",
        "    text = 'Equip {2}'",
        "class GleamOfDeathAbility1:",
        ("    text = 'Mill six cards, then put all instant and sorcery cards from among them "
         "into your hand. (Then exile this card. You may cast the artifact later from exile.)'"),
        "class GlamdringFoehammer(Artifact):",
        "class GleamOfDeath(Sorcery):",
    ]
    assert not gen.generate(card_dir, make_stub=True)
    assert not gen.generate(card_dir)


def test_an_implementation_keeps_its_class_and_gains_ability_classes(tmp_path):
    card_dir = _card_dir(tmp_path, {
        "name": "Llanowar Elves", "type_line": "Creature — Elf Druid",
        "oracle_text": "{T}: Add {G}.", "keywords": [],
    })
    implementation = (
        '"""Card implementation for Llanowar Elves."""\n\n'
        "from engine.card import Creature\n\n\n"
        "class LlanowarElves(Creature):\n    pass\n"
    )
    (card_dir / "card_impl.py").write_text(implementation)
    assert gen.generate(card_dir)
    source = (card_dir / "card_impl.py").read_text()
    assert source.index("class LlanowarElvesAbility1:") < source.index("class LlanowarElves(")
    assert "    text = '{T}: Add {G}.'" in source
    assert not gen.generate(card_dir)


@pytest.mark.parametrize("card_id", sorted(p.parent.name for p in FDN.glob("*/card_spec.json")))
def test_known_best_printed_classes_are_up_to_date(card_id):
    card_dir = FDN / card_id
    assert gen.render(card_dir) == (card_dir / "card_impl.py").read_text()


_INSTANTIATE = """
import importlib.util, json, sys
from engine.card import CardImpl
result = {}
for i, path in enumerate(sys.argv[1:]):
    spec = importlib.util.spec_from_file_location(f"stub_{i}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, cls in vars(module).items():
        if isinstance(cls, type) and issubclass(cls, CardImpl) and cls.__module__ == module.__name__:
            card = cls()
            result[card.name] = {
                "class": name,
                "mana_cost": str(card.mana_cost),
                "card_types": sorted(t.name for t in card.card_types),
                "supertypes": sorted(t.name for t in card.supertypes),
                "subtypes": sorted(card.subtypes),
                "power": getattr(card, "base_power", None),
                "toughness": getattr(card, "base_toughness", None),
                "loyalty": getattr(card, "starting_loyalty", None),
            }
print(json.dumps(result))
"""


def _instantiate(*card_dirs: Path) -> dict[str, dict]:
    """Instantiate every face class in ``card_dirs`` against the Known-Best engine."""
    workspace = REPO / "known_best/workspace"
    completed = subprocess.run(
        [sys.executable, "-c", _INSTANTIATE, *(str(d / "card_impl.py") for d in card_dirs)],
        cwd=workspace, env={"PYTHONPATH": str(workspace)}, capture_output=True, text=True, check=True,
    )
    return json.loads(completed.stdout)


def _spec_dir(tmp_path: Path, spec_path: Path) -> Path:
    card_dir = tmp_path / spec_path.parent.name
    card_dir.mkdir()
    (card_dir / "card_spec.json").write_text(spec_path.read_text())
    return card_dir


def test_generated_stubs_instantiate_with_their_printed_characteristics(tmp_path):
    hall = REPO / "benchmarks/fra-hard/workspace/cards/fra/fra_179/card_spec.json"
    fdn = [FDN / card / "card_spec.json" for card in ("fdn_7", "fdn_238", "fdn_272", "fdn_1", "fdn_234")]
    card_dirs = [_spec_dir(tmp_path, path) for path in (hall, *fdn)]
    for card_dir in card_dirs[:3]:
        assert gen.generate(card_dir, make_stub=True)
    for card_dir in card_dirs[3:]:
        assert gen.generate(card_dir)  # no card_impl.py yet, so a stub is generated
    for card_dir in card_dirs:
        assert not gen.generate(card_dir)
    cards = _instantiate(*card_dirs)

    hall_of_echoes, plains = cards["Hall of Echoes"], cards["Plains"]
    assert hall_of_echoes["mana_cost"] == plains["mana_cost"]
    assert hall_of_echoes["card_types"] == ["LAND"]
    assert plains["supertypes"] == ["BASIC"]
    assert plains["subtypes"] == ["Plains"]
    barricade = cards["Crystal Barricade"]
    assert barricade["class"] == "CrystalBarricade"
    assert barricade["card_types"] == ["ARTIFACT", "CREATURE"]
    assert (barricade["power"], barricade["toughness"]) == (0, 4)
    aberration = cards["Consuming Aberration"]
    assert (aberration["power"], aberration["toughness"]) == (0, 0)
    sire = cards["Sire of Seven Deaths"]
    assert (sire["power"], sire["toughness"]) == (7, 7)
    vivien = cards["Vivien Reid"]
    assert (vivien["card_types"], vivien["supertypes"], vivien["loyalty"]) == (["PLANESWALKER"], ["LEGENDARY"], 5)


def test_both_faces_of_a_generated_stub_instantiate(tmp_path):
    card_dir = _card_dir(tmp_path, GLAMDRING)
    gen.generate(card_dir, make_stub=True)
    cards = _instantiate(card_dir)
    glamdring, gleam = cards["Glamdring, Foe-hammer"], cards["Gleam of Death"]
    assert (glamdring["card_types"], glamdring["supertypes"], glamdring["subtypes"]) == (
        ["ARTIFACT"], ["LEGENDARY"], ["Equipment"])
    assert (gleam["card_types"], gleam["subtypes"]) == (["SORCERY"], ["Adventure"])
    assert gleam["mana_cost"] != glamdring["mana_cost"]


def test_a_type_line_without_a_supported_card_type_is_rejected(tmp_path):
    card_dir = _card_dir(tmp_path, {"name": "Nothing", "type_line": "Kindred — Elf", "oracle_text": ""})
    with pytest.raises(ValueError, match="no supported card type"):
        gen.generate(card_dir, make_stub=True)
