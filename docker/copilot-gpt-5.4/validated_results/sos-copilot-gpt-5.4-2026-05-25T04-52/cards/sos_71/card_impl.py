"""Card implementation for Wisdom of Ages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Instant, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class WisdomOfAges(Sorcery):
    """Wisdom of Ages."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wisdom of Ages")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Return all instant and sorcery cards from your graveyard to your hand. "
            "You have no maximum hand size for the rest of the game.\n"
            "Exile Wisdom of Ages.",
        )
        super().__init__(**kwargs)
        self.always_exile_on_resolve = True
        self._rest_of_game_no_maximum_hand_size_source = object()

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        graveyard = game.get_graveyard(controller)
        for card in list(graveyard.get_all()):
            if not isinstance(card, (Instant, Sorcery)):
                continue
            move_to_zone(game, card, Zone.GRAVEYARD, Zone.HAND)

        controller.grant_no_maximum_hand_size(self._rest_of_game_no_maximum_hand_size_source)
