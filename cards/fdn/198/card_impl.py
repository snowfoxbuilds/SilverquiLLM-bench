from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost


class FlamewakePhoenix(Creature):
    """Flamewake Phoenix."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Flamewake Phoenix")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}{R}"))
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.HASTE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Phoenix"}
        super().__init__(**kwargs)
