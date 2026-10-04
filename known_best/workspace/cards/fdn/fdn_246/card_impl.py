"""Card implementation for Swiftblade Vindicator."""

from __future__ import annotations
from typing import TYPE_CHECKING

from engine.creatures import make_vanilla
from engine.types import Keyword

if TYPE_CHECKING:
    from cards.registry import CardRegistry


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class SwiftbladeVindicatorAbility1:
    text = 'Double strike (This creature deals both first-strike and regular combat damage.)'


class SwiftbladeVindicatorAbility2:
    text = "Vigilance (Attacking doesn't cause this creature to tap.)"


class SwiftbladeVindicatorAbility3:
    text = "Trample (This creature can deal excess combat damage to the player or planeswalker it's attacking.)"


# endregion Printed abilities


SwiftbladeVindicator = make_vanilla(
    "Swiftblade Vindicator", "{R}{W}", 1, 1,
    keywords=Keyword.DOUBLE_STRIKE | Keyword.VIGILANCE | Keyword.TRAMPLE,
    creature_types={"Human", "Soldier"},
)
