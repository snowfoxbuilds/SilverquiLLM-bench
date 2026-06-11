"""Card implementation for Mind into Matter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class MindIntoMatter(Sorcery):
    """Mind into Matter — {X}{G}{U} — Sorcery.

    Draw X cards. Then you may put a permanent card with mana value X or less
    from your hand onto the battlefield tapped.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mind into Matter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}{G}{U}"))
        super().__init__(**kwargs)
        self.x_value: int = 0

    def on_resolve(self, game: "GameState") -> None:
        """Draw X cards, then put a permanent with MV <= X onto BF tapped."""
        if self.controller is None:
            return
        x = getattr(self, 'x_value', 0)

        # Draw X cards from library into hand
        library = game.get_library(self.controller)
        hand = game.get_hand(self.controller)
        for _ in range(x):
            lib_cards = library.get_all()
            if not lib_cards:
                break
            # Draw from the first available card in library
            drawn = lib_cards[0]
            library.remove(drawn)
            hand.add(drawn)

        # Put a permanent card with MV <= X from hand onto battlefield tapped
        hand_cards = hand.get_all()
        # Find first eligible permanent card
        permanent_types = {CardType.CREATURE, CardType.ENCHANTMENT, CardType.ARTIFACT,
                          CardType.PLANESWALKER, CardType.LAND}
        chosen = None
        for card in hand_cards:
            card_types = getattr(card, 'card_types', set())
            if card_types & permanent_types:
                mv = getattr(card, 'mana_cost', ManaCost())
                if mv.cmc <= x:
                    chosen = card
                    break

        if chosen is not None:
            hand.remove(chosen)
            chosen.is_tapped = True
            chosen.controller = self.controller
            game.get_battlefield(self.controller).add(chosen)
