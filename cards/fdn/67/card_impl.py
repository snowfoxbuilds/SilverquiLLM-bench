from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class RevengeOfTheRats(Sorcery):
    """Revenge of the Rats."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Revenge of the Rats")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}{B}"))
        super().__init__(**kwargs)
