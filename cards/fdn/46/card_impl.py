from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class LunarInsight(Sorcery):
    """Lunar Insight."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lunar Insight")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        super().__init__(**kwargs)
