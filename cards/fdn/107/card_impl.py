from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class MossbornHydra(Creature):
    """Mossborn Hydra."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mossborn Hydra")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("keywords", Keyword.TRAMPLE)
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 0)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Elemental", "Hydra"}
        super().__init__(**kwargs)
