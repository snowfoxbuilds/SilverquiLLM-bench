"""Card implementation for Thornwood Falls."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class ThornwoodFallsAbility1:
    text = 'This land enters tapped.'


class ThornwoodFallsAbility2:
    text = 'When this land enters, you gain 1 life.'


class ThornwoodFallsAbility3:
    text = '{T}: Add {G} or {U}.'


# endregion Printed abilities


ThornwoodFalls = make_gainlife_tapland(
    "Thornwood Falls", (ManaType.GREEN, ManaType.BLUE), 269, mana_printed=ThornwoodFallsAbility3
)
