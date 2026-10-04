"""Card implementation for Blossoming Sands."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class BlossomingSandsAbility1:
    text = 'This land enters tapped.'


class BlossomingSandsAbility2:
    text = 'When this land enters, you gain 1 life.'


class BlossomingSandsAbility3:
    text = '{T}: Add {G} or {W}.'


# endregion Printed abilities


BlossomingSands = make_gainlife_tapland(
    "Blossoming Sands", (ManaType.GREEN, ManaType.WHITE), 260, mana_printed=BlossomingSandsAbility3
)
