from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class BlasphemousEdict(Sorcery):
    """Blasphemous Edict."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Blasphemous Edict")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{B}"))
        super().__init__(**kwargs)
