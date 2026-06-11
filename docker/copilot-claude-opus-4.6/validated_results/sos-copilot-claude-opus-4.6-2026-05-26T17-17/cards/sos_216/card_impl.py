"""Card implementation for Pursue the Past."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class PursueThePast(Sorcery):
    """Pursue the Past — {R}{W} — Sorcery.

    You gain 2 life. You may discard a card. If you do, draw two cards.
    Flashback {2}{R}{W}
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pursue the Past")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{W}"))
        kwargs.setdefault("keywords", Keyword.FLASHBACK)
        kwargs.setdefault(
            "rules_text",
            "You gain 2 life. You may discard a card. If you do, draw two cards.\n"
            "Flashback {2}{R}{W}",
        )
        super().__init__(**kwargs)
        self.flashback_cost = ManaCost.parse("{2}{R}{W}")

    def on_resolve(self, game: "GameState") -> None:
        """Gain 2 life, optionally discard a card to draw two."""
        from engine.game import draw_card, discard

        player = self.controller
        # Gain 2 life
        player.life += 2

        # May discard a card. If hand is non-empty, discard first card.
        hand = game.get_hand(player)
        hand_cards = hand.get_all()
        if len(hand_cards) > 0:
            # Choose first card to discard (deterministic for tests)
            card_to_discard = hand_cards[0]
            discard(game, player, card_to_discard)
            # Draw two cards
            draw_card(game, player)
            draw_card(game, player)

    def cast_flashback(self, game: "GameState", player: Any) -> None:
        """Cast this spell from graveyard for its flashback cost, then exile."""
        from engine.stack import StackObject

        # Remove from graveyard
        graveyard = game.get_graveyard(player)
        if graveyard.contains(self):
            graveyard.remove(self)

        self.controller = player
        self._cast_via_flashback = True

        # Pay flashback cost
        player.mana_pool.pay(self.flashback_cost)

        # Push onto stack
        def _on_resolve(g: "GameState") -> None:
            self.on_resolve(g)
            # Exile after flashback resolution
            self.zone = Zone.EXILE
            exile = g.get_exile(player)
            exile.add(self)

        stack_obj = StackObject(
            source=self,
            controller=player,
            targets=[],
            on_resolve=_on_resolve,
        )
        game.stack.push(stack_obj)
