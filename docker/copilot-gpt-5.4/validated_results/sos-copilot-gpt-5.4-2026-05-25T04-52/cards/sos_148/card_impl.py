"""Card implementation for Follow the Lumarets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Sorcery
from benchmarks.sos.workspace.engine.game import (
    look_at_cards,
    put_cards_on_bottom_in_random_order,
    reveal_cards,
)
from benchmarks.sos.workspace.engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class FollowTheLumarets(Sorcery):
    """Follow the Lumarets."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Follow the Lumarets")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        library = game.get_library(controller)
        looked_at = list(library.top(4))
        if not looked_at:
            return
        look_at_cards(game, controller, looked_at, source=self, reason="Follow the Lumarets")
        for card in looked_at:
            library.remove(card)

        remaining = list(looked_at)
        eligible = [
            card
            for card in remaining
            if getattr(card, "card_types", set()) & {CardType.CREATURE, CardType.LAND}
        ]
        max_picks = 2 if getattr(controller, "life_gained_this_turn", 0) > 0 else 1
        chosen_cards: list[Any] = []
        for _ in range(min(max_picks, len(eligible))):
            choice = controller.choose_card(
                list(eligible),
                "Choose a creature or land card to put into your hand",
            )
            if choice is None or choice not in eligible:
                break
            chosen_cards.append(choice)
            eligible.remove(choice)
            remaining.remove(choice)
        if chosen_cards:
            reveal_cards(game, controller, chosen_cards, source=self, reason="Follow the Lumarets")
            hand = game.get_hand(controller)
            for card in chosen_cards:
                hand.add(card)
        if remaining:
            put_cards_on_bottom_in_random_order(
                game,
                controller,
                remaining,
                source=self,
                reason="Follow the Lumarets",
            )
