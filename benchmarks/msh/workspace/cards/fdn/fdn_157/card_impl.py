"""Card implementation for Lightshell Duo."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.card_queries import query_yes_no
from engine.types import Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class LightshellDuo(Creature):
    """Lightshell Duo — {3}{U} — 3/4 — Rat Otter — Prowess.

    When this creature enters, surveil 2.

    FDN collector number 157.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Lightshell Duo")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault("subtypes", {"Rat", "Otter"})
        kwargs.setdefault("keywords", Keyword.PROWESS)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Prowess\nWhen this creature enters, surveil 2.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: surveil 2."""
        controller = self.controller
        if controller is None:
            return
        library = controller.zones[Zone.LIBRARY]
        cards = list(library.get_all())
        if not cards:
            return
        top_cards = cards[-min(2, len(cards)):]
        for card in reversed(top_cards):
            put_in_gy = query_yes_no(
                game,
                controller,
                f"Surveil: Put {getattr(card, 'name', 'card')} into your graveyard?",
                source_card=self,
            )
            if put_in_gy:
                library.remove(card)
                controller.zones[Zone.GRAVEYARD].add(card)
