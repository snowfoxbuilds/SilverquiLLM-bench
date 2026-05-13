from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class Overrun(Sorcery):
    """Overrun."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Overrun")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}{G}{G}"))
        super().__init__(**kwargs)
