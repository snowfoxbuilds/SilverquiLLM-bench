from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class ZimoneParadoxSculptor(Creature):
    """Zimone, Paradox Sculptor."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zimone, Paradox Sculptor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}{U}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 4)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Human", "Wizard"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
