"""Card implementation for Elementalist Adept."""

from __future__ import annotations
from typing import TYPE_CHECKING

from engine.creatures import make_vanilla
from engine.types import Keyword

if TYPE_CHECKING:
    from cards.registry import CardRegistry


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class ElementalistAdeptAbility1:
    text = 'Flash (You may cast this spell any time you could cast an instant.)'


class ElementalistAdeptAbility2:
    text = 'Prowess (Whenever you cast a noncreature spell, this creature gets +1/+1 until end of turn.)'


# endregion Printed abilities


ElementalistAdept = make_vanilla(
    "Elementalist Adept", "{1}{U}", 2, 1,
    keywords=Keyword.FLASH,
    creature_types={"Human", "Wizard"},
)
