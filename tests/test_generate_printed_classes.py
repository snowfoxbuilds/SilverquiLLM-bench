"""The printed-class generator (DECISION-MODEL.md › Printed identity)."""

from __future__ import annotations

import importlib.util
import json
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
