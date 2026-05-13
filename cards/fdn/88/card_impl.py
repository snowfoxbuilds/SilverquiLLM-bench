from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class GoblinNegotiation(Sorcery):
    """Goblin Negotiation."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Goblin Negotiation")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{R}{R}"))
        super().__init__(**kwargs)
