from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class HeroicReinforcements(Sorcery):
    """Heroic Reinforcements."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Heroic Reinforcements")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}{W}"))
        super().__init__(**kwargs)
