from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class LathrilBladeOfTheElves(Creature):
    """Lathril, Blade of the Elves."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lathril, Blade of the Elves")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}{G}"))
        kwargs.setdefault("keywords", Keyword.MENACE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elf", "Noble"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
