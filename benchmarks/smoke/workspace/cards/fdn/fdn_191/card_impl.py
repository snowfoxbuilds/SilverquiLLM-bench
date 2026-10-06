"""Card implementation for Brazen Scourge."""

from __future__ import annotations
from typing import TYPE_CHECKING

from engine.creatures import make_vanilla
from engine.types import Keyword

if TYPE_CHECKING:
    from cards.registry import CardRegistry


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class BrazenScourgeAbility1:
    text = 'Haste (This creature can attack and {T} as soon as it comes under your control.)'


# endregion Printed abilities


BrazenScourge = make_vanilla(
    "Brazen Scourge", "{1}{R}{R}", 3, 3,
    keywords=Keyword.HASTE,
    creature_types={"Gremlin"},
)
