"""Card implementation for Borrowed Knowledge."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Mode, Sorcery
from benchmarks.sos.workspace.engine.events import DrawsCardTriggeredEvent
from benchmarks.sos.workspace.engine.game import discard
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class BorrowedKnowledge(Sorcery):
    """Borrowed Knowledge."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Borrowed Knowledge")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}{W}"))
        super().__init__(**kwargs)
        self.selected_mode: int = 0

    def get_modes(self) -> list[Mode]:
        return [
            Mode(
                name="Match opponent's hand",
                description="Discard your hand, then draw cards equal to the number of cards in target opponent's hand.",
            ),
            Mode(
                name="Replace discarded cards",
                description="Discard your hand, then draw cards equal to the number of cards discarded this way.",
            ),
        ]

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        if self.selected_mode != 0:
            return []
        controller = self.controller
        return [
            TargetRequirement(
                filter_fn=lambda obj, current_controller=controller: (
                    hasattr(obj, "zones") and obj is not current_controller
                ),
                description="target opponent's hand",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def _discard_hand(self, game: GameState) -> int:
        controller = self.controller
        if controller is None:
            return 0
        hand_cards = list(game.get_hand(controller).get_all())
        for card in hand_cards:
            discard(game, controller, card)
        return len(hand_cards)

    def _draw_cards(self, game: GameState, count: int) -> None:
        controller = self.controller
        if controller is None:
            return
        library = game.get_library(controller)
        hand = game.get_hand(controller)
        for _ in range(count):
            ordered_cards = library.get_all()
            if not ordered_cards:
                controller.drawn_from_empty_library = True
                return
            card = ordered_cards[0]
            library.remove(card)
            hand.add(card)
            controller.cards_drawn_this_turn = getattr(controller, "cards_drawn_this_turn", 0) + 1
            game.trigger_manager.fire_event(
                game,
                DrawsCardTriggeredEvent(player=controller, card=card),
            )

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        discarded_count = self._discard_hand(game)
        draw_count = discarded_count
        if self.selected_mode == 0:
            target_opponent = getattr(self, "chosen_targets", [None])[0]
            if hasattr(target_opponent, "zones"):
                draw_count = len(game.get_hand(target_opponent).get_all())
            else:
                draw_count = 0

        self._draw_cards(game, draw_count)
