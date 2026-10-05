"""Card implementation for Swiftwater Cliffs."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class SwiftwaterCliffsAbility1:
    text = 'This land enters tapped.'


class SwiftwaterCliffsAbility2:
    text = 'When this land enters, you gain 1 life.'


class SwiftwaterCliffsAbility3:
    text = '{T}: Add {U} or {R}.'


# endregion Printed abilities


SwiftwaterCliffs = make_gainlife_tapland(
    "Swiftwater Cliffs", (ManaType.BLUE, ManaType.RED), 268, mana_printed=SwiftwaterCliffsAbility3, enters_printed=SwiftwaterCliffsAbility2
)
