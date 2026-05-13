from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class InspirationFromBeyond(Sorcery):
    """Inspiration from Beyond."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Inspiration from Beyond")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        super().__init__(**kwargs)
