"""Card implementation for Vampire Nighthawk."""

from __future__ import annotations
from typing import TYPE_CHECKING

from engine.creatures import make_vanilla
from engine.types import Keyword

if TYPE_CHECKING:
    from cards.registry import CardRegistry


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class VampireNighthawkAbility1:
    text = 'Flying'


class VampireNighthawkAbility2:
    text = 'Deathtouch (Any amount of damage this deals to a creature is enough to destroy it.)'


class VampireNighthawkAbility3:
    text = 'Lifelink (Damage dealt by this creature also causes you to gain that much life.)'


# endregion Printed abilities


VampireNighthawk = make_vanilla(
    "Vampire Nighthawk", "{1}{B}{B}", 2, 3,
    keywords=Keyword.FLYING | Keyword.DEATHTOUCH | Keyword.LIFELINK,
    creature_types={"Vampire", "Shaman"},
)
