from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class PreposterousProportions(Sorcery):
    """Preposterous Proportions."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Preposterous Proportions")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{G}{G}"))
        super().__init__(**kwargs)
