from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class RiseOfTheDarkRealms(Sorcery):
    """Rise of the Dark Realms."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rise of the Dark Realms")
        kwargs.setdefault("mana_cost", ManaCost.parse("{7}{B}{B}"))
        super().__init__(**kwargs)
