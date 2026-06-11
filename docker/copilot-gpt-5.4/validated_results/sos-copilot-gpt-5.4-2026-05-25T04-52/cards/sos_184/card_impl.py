"""Card implementation for Dina's Guidance."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.game import reveal_cards, shuffle_library
from benchmarks.sos.workspace.engine.types import ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class DinasGuidance(Instant):
    """Dina's Guidance."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dina's Guidance")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{G}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return
        library = game.get_library(controller)
        creatures = [card for card in library.get_all() if isinstance(card, Creature)]
        chosen = None
        if creatures:
            try:
                chosen = controller.choose_card(creatures, "Choose a creature card")
            except Exception:
                chosen = creatures[0]
            if chosen not in creatures:
                chosen = creatures[0]
        if isinstance(chosen, Creature):
            reveal_cards(game, controller, [chosen], source=self, reason=self.name)
            try:
                destination = controller.choose([Zone.HAND, Zone.GRAVEYARD], "Choose hand or graveyard")
            except Exception:
                destination = Zone.HAND
            if destination not in {Zone.HAND, Zone.GRAVEYARD}:
                destination = Zone.HAND
            move_to_zone(game, chosen, Zone.LIBRARY, destination)
        shuffle_library(game, controller, source=self, reason=self.name)
