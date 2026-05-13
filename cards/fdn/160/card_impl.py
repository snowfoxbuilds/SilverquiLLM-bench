from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant
from engine.types import ManaCost


class AnOfferYouCantRefuse(Instant):
    """An Offer You Can't Refuse."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "An Offer You Can't Refuse")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)
