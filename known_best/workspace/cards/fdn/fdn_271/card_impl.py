"""Card implementation for Wind-Scarred Crag."""

from __future__ import annotations

from engine.types import ManaType

from cards.fdn.gainlife_taplands import make_gainlife_tapland


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class WindScarredCragAbility1:
    text = 'This land enters tapped.'


class WindScarredCragAbility2:
    text = 'When this land enters, you gain 1 life.'


class WindScarredCragAbility3:
    text = '{T}: Add {R} or {W}.'


# endregion Printed abilities


WindScarredCrag = make_gainlife_tapland(
    "Wind-Scarred Crag", (ManaType.RED, ManaType.WHITE), 271, mana_printed=WindScarredCragAbility3
)
