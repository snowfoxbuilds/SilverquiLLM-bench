"""Card implementation for Healer's Hawk."""

from __future__ import annotations
from typing import TYPE_CHECKING

from engine.creatures import make_vanilla
from engine.types import Keyword

if TYPE_CHECKING:
    from cards.registry import CardRegistry


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class HealersHawkAbility1:
    text = 'Flying'


class HealersHawkAbility2:
    text = 'Lifelink (Damage dealt by this creature also causes you to gain that much life.)'


# endregion Printed abilities


HealersHawk = make_vanilla(
    "Healer's Hawk", "{W}", 1, 1,
    keywords=Keyword.FLYING | Keyword.LIFELINK,
    creature_types={"Bird"},
)
