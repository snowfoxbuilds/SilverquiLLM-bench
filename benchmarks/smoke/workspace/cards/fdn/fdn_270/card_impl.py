"""Card implementation for Tranquil Cove."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class TranquilCoveAbility1:
    text = 'This land enters tapped.'


class TranquilCoveAbility2:
    text = 'When this land enters, you gain 1 life.'


class TranquilCoveAbility3:
    text = '{T}: Add {W} or {U}.'


# endregion Printed abilities


TranquilCove = make_gainlife_tapland(
    "Tranquil Cove", (ManaType.WHITE, ManaType.BLUE), 270, mana_printed=TranquilCoveAbility3, enters_printed=TranquilCoveAbility2
)
