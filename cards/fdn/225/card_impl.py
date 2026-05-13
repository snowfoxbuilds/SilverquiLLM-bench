from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class GrowFromTheAshes(Sorcery):
    """Grow from the Ashes."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Grow from the Ashes")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        super().__init__(**kwargs)
