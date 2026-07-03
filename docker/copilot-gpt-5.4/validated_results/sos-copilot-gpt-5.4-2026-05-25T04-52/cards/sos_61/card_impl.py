"""Card implementation for Muse's Encouragement."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.game import create_token
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class MusesEncouragement(Instant):
    """Muse's Encouragement."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Muse's Encouragement")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Create a 3/3 blue and red Elemental creature token with flying.\n"
            "Surveil 2.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        token = Creature(
            name="Elemental",
            owner=controller,
            controller=controller,
            subtypes={"Elemental"},
            keywords=Keyword.FLYING,
            base_power=3,
            base_toughness=3,
        )
        token.colors = {Color.BLUE, Color.RED}
        token.snapshot_current_characteristics()
        create_token(game, controller, token)

        library = game.get_library(controller)
        for card in reversed(library.top(2)):
            if controller.choose_yes_no(
                f"Put {getattr(card, 'name', 'this card')} into your graveyard?"
            ):
                move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)
