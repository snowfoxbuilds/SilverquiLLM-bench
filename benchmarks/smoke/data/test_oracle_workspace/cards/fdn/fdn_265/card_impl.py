"""Card implementation for Rugged Highlands."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class RuggedHighlandsAbility1:
    text = 'This land enters tapped.'


class RuggedHighlandsAbility2:
    text = 'When this land enters, you gain 1 life.'


class RuggedHighlandsAbility3:
    text = '{T}: Add {R} or {G}.'


# endregion Printed abilities


RuggedHighlands = make_gainlife_tapland(
    "Rugged Highlands", (ManaType.RED, ManaType.GREEN), 265, mana_printed=RuggedHighlandsAbility3
)
