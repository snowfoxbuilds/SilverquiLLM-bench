from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class MacabreWaltz(Sorcery):
    """Macabre Waltz."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Macabre Waltz")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        super().__init__(**kwargs)
