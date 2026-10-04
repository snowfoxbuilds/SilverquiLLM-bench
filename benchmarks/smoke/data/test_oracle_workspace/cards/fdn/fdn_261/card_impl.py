"""Card implementation for Dismal Backwater."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class DismalBackwaterAbility1:
    text = 'This land enters tapped.'


class DismalBackwaterAbility2:
    text = 'When this land enters, you gain 1 life.'


class DismalBackwaterAbility3:
    text = '{T}: Add {U} or {B}.'


# endregion Printed abilities


DismalBackwater = make_gainlife_tapland(
    "Dismal Backwater", (ManaType.BLUE, ManaType.BLACK), 261, mana_printed=DismalBackwaterAbility3
)
