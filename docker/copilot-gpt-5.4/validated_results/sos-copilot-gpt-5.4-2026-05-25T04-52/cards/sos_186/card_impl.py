"""Card implementation for Embrace the Paradox."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Instant, Land
from benchmarks.sos.workspace.engine.game import draw_card
from benchmarks.sos.workspace.engine.types import ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class EmbraceTheParadox(Instant):
    """Embrace the Paradox."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Embrace the Paradox")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{U}"))
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        for _ in range(3):
            draw_card(game, controller)

        lands = [card for card in game.get_hand(controller).get_all() if isinstance(card, Land)]
        if not lands:
            return

        try:
            put_land = controller.choose_yes_no(
                "Put a land card from your hand onto the battlefield tapped?"
            )
        except Exception:
            put_land = False
        if not put_land:
            return

        try:
            chosen_land = controller.choose_card(lands, "land card to put onto the battlefield tapped")
        except Exception:
            chosen_land = None
        if chosen_land not in lands:
            chosen_land = lands[0]

        chosen_land.is_tapped = True
        move_to_zone(game, chosen_land, Zone.HAND, Zone.BATTLEFIELD)
