from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class FirespitterWhelp(Creature):
    """Firespitter Whelp."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Firespitter Whelp")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Dragon"}
        super().__init__(**kwargs)
