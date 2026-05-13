from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class InvoluntaryEmployment(Sorcery):
    """Involuntary Employment."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Involuntary Employment")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        super().__init__(**kwargs)
