from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class Boltwave(Sorcery):
    """Boltwave."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Boltwave")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)
