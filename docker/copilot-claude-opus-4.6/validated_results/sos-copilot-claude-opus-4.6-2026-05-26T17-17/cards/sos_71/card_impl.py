"""Card implementation for Wisdom of Ages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class WisdomOfAges(Sorcery):
    """Wisdom of Ages — {4}{U}{U}{U} — Sorcery.

    Return all instant and sorcery cards from your graveyard to your hand.
    You have no maximum hand size for the rest of the game.
    Exile Wisdom of Ages.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wisdom of Ages")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}{U}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        controller = self.controller or self.owner

        # Return all instant and sorcery cards from graveyard to hand
        graveyard = game.get_graveyard(controller)
        hand = game.get_hand(controller)
        to_return = [
            c for c in graveyard.get_all()
            if CardType.INSTANT in getattr(c, "card_types", set())
            or CardType.SORCERY in getattr(c, "card_types", set())
        ]
        for card in to_return:
            graveyard.remove(card)
            hand.add(card)

        # No maximum hand size for the rest of the game
        controller.max_hand_size = float('inf')

        # Exile Wisdom of Ages
        exile = game.get_exile(controller)
        # Remove from wherever it currently is
        for zone in [Zone.HAND, Zone.GRAVEYARD]:
            z = controller.zones[zone]
            if z.contains(self):
                z.remove(self)
                break
        exile.add(self)
