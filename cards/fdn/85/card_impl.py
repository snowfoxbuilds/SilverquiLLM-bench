from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class Electroduplicate(Sorcery):
    """Electroduplicate."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Electroduplicate")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        super().__init__(**kwargs)
