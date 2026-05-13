"""Card implementation for Scrawling Crawler."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ArtifactCreature
from engine.types import ManaCost


class ScrawlingCrawler(ArtifactCreature):
    """Scrawling Crawler — {3} — 3/2 Phyrexian Construct.
    Upkeep: each player draws. Opponent draws → loses 1 life."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Scrawling Crawler")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Phyrexian", "Construct"}
        kwargs.setdefault(
            "rules_text",
            "At the beginning of your upkeep, each player draws a card.\n"
            "Whenever an opponent draws a card, that player loses 1 life.",
        )
        super().__init__(**kwargs)
