from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost


class BrasssBounty(Sorcery):
    """Brass's Bounty."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Brass's Bounty")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}{R}"))
        super().__init__(**kwargs)
