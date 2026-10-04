"""Card implementation for Bloodfell Caves."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class BloodfellCavesAbility1:
    text = 'This land enters tapped.'


class BloodfellCavesAbility2:
    text = 'When this land enters, you gain 1 life.'


class BloodfellCavesAbility3:
    text = '{T}: Add {B} or {R}.'


# endregion Printed abilities


BloodfellCaves = make_gainlife_tapland(
    "Bloodfell Caves", (ManaType.BLACK, ManaType.RED), 259, mana_printed=BloodfellCavesAbility3
)
