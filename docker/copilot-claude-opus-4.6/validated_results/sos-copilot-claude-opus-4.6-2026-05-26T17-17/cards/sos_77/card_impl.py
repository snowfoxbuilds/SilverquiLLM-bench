"""Card implementation for Cost of Brilliance."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class CostOfBrilliance(Sorcery):
    """Cost of Brilliance — {2}{B} — Sorcery.

    Target player draws two cards and loses 2 life.
    Put a +1/+1 counter on up to one target creature.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cost of Brilliance")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        targets = getattr(self, "chosen_targets", [])
        if not targets:
            return
        # First target is the player
        player = targets[0]
        # Draw two cards
        library = game.get_library(player)
        hand = game.get_hand(player)
        for _ in range(2):
            cards = library.get_all()
            if cards:
                card = cards[-1]
                library.remove(card)
                hand.add(card)
        # Lose 2 life
        player.life -= 2
        # Second target (optional) is a creature to get +1/+1 counter
        if len(targets) > 1:
            creature = targets[1]
            if creature is not None:
                creature.plus_one_counters += 1
                creature._base_plus_one_counters = creature.plus_one_counters
