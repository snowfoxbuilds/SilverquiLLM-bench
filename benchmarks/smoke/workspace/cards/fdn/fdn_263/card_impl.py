"""Card implementation for Jungle Hollow."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class JungleHollowAbility1:
    text = 'This land enters tapped.'


class JungleHollowAbility2:
    text = 'When this land enters, you gain 1 life.'


class JungleHollowAbility3:
    text = '{T}: Add {B} or {G}.'


# endregion Printed abilities


JungleHollow = make_gainlife_tapland(
    "Jungle Hollow", (ManaType.BLACK, ManaType.GREEN), 263, mana_printed=JungleHollowAbility3, enters_printed=JungleHollowAbility2
)
