"""Card implementation for Zimone's Experiment."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Land, Sorcery
from benchmarks.sos.workspace.engine.game import (
    look_at_cards,
    put_cards_on_bottom_in_random_order,
    reveal_cards,
)
from benchmarks.sos.workspace.engine.types import ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class ZimonesExperiment(Sorcery):
    """Zimone's Experiment."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zimone's Experiment")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        library = game.get_library(controller)
        looked_at = list(library.top(5))
        if not looked_at:
            return

        look_at_cards(game, controller, looked_at, source=self, reason="Zimone's Experiment")

        eligible = [card for card in looked_at if isinstance(card, (Creature, Land))]
        chosen_cards: list[Any] = []
        for _ in range(min(2, len(eligible))):
            choice = controller.choose_card(
                list(eligible),
                "Choose up to two creature and/or land cards to reveal",
            )
            if choice is None or choice not in eligible:
                break
            chosen_cards.append(choice)
            eligible.remove(choice)

        if chosen_cards:
            reveal_cards(game, controller, chosen_cards, source=self, reason="Zimone's Experiment")

        remaining = [card for card in looked_at if card not in chosen_cards]
        for card in chosen_cards:
            if isinstance(card, Land):
                card.is_tapped = True
                move_to_zone(game, card, Zone.LIBRARY, Zone.BATTLEFIELD)
            elif isinstance(card, Creature):
                move_to_zone(game, card, Zone.LIBRARY, Zone.HAND)

        if remaining:
            put_cards_on_bottom_in_random_order(
                game,
                controller,
                remaining,
                source=self,
                reason="Zimone's Experiment",
            )
