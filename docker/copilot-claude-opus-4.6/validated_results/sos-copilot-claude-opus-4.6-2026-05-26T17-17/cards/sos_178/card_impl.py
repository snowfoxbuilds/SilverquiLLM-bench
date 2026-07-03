"""Card implementation for Borrowed Knowledge."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class BorrowedKnowledge(Sorcery):
    """Borrowed Knowledge — {2}{R}{W} — Sorcery.

    Choose one —
    • Discard your hand, then draw cards equal to the number of cards in
      target opponent's hand.
    • Discard your hand, then draw cards equal to the number of cards
      discarded this way.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Borrowed Knowledge')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{R}{W}'))
        super().__init__(**kwargs)

    def on_resolve(self, game: 'GameState') -> None:
        controller = getattr(self, 'controller', None) or getattr(self, 'owner', None)
        if controller is None:
            return

        # Determine mode: if there's a target opponent, use mode 1; else mode 2
        targets = getattr(self, '_explicit_targets', None) or getattr(self, 'chosen_targets', None) or []
        opponent_target = None
        for t in targets:
            # A target that is a Player (opponent)
            if hasattr(t, 'life') and t is not controller:
                opponent_target = t
                break

        hand = game.get_hand(controller)
        hand_cards = [c for c in hand.get_all() if c is not self]

        # Discard the hand
        num_discarded = len(hand_cards)
        gy = game.get_graveyard(controller)
        for card in hand_cards:
            hand.remove(card)
            gy.add(card)

        # Remove self from hand if still there
        if hand.contains(self):
            hand.remove(self)

        # Determine draw count
        if opponent_target is not None:
            # Mode 1: draw equal to opponent's hand size
            opp_hand = game.get_hand(opponent_target)
            draw_count = len(opp_hand)
        else:
            # Mode 2: draw equal to number discarded
            draw_count = num_discarded

        # Draw cards
        from engine.game import draw_card
        for _ in range(draw_count):
            draw_card(game, controller)
