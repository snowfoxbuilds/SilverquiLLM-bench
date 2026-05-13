from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class GenesisWave(Sorcery):
    """Genesis Wave."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Genesis Wave")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{G}{G}{G}"))
        super().__init__(**kwargs)
