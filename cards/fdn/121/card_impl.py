from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype


class KomaWorldEater(Creature):
    """Koma, World-Eater."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Koma, World-Eater")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{G}{U}{U}"))
        kwargs.setdefault("keywords", Keyword.TRAMPLE | Keyword.WARD)
        kwargs.setdefault("base_power", 8)
        kwargs.setdefault("base_toughness", 12)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Serpent"}
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        super().__init__(**kwargs)
