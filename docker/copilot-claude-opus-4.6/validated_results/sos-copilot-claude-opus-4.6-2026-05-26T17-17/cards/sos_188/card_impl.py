"""Card implementation for Fix What's Broken."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class FixWhatsBroken(Sorcery):
    """Fix What's Broken — {2}{W}{B} — Sorcery.

    As an additional cost to cast this spell, pay X life.
    Return each artifact and creature card with mana value X from your
    graveyard to the battlefield.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fix What's Broken")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        super().__init__(**kwargs)
        self.x_value: int = 0

    def on_resolve(self, game: "GameState") -> None:
        """Return each artifact/creature with mana value X from graveyard to battlefield."""
        controller = self.controller
        if controller is None:
            return

        x = self.x_value
        graveyard = game.get_graveyard(controller)
        bf = game.get_battlefield(controller)

        # Find matching cards
        to_return = []
        for card in graveyard.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.CREATURE not in card_types and CardType.ARTIFACT not in card_types:
                continue
            mana_cost = getattr(card, "mana_cost", None)
            if mana_cost is None:
                continue
            if mana_cost.cmc == x:
                to_return.append(card)

        for card in to_return:
            graveyard.remove(card)
            bf.add(card)
