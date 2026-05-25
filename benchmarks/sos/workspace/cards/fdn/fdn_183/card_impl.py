"""Card implementation for Rise of the Dark Realms."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RiseOfTheDarkRealms(Sorcery):
    """Rise of the Dark Realms — {7}{B}{B} — Sorcery.

    Put all creature cards from all graveyards onto the battlefield under
    your control.

    FDN collector number 183.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rise of the Dark Realms")
        kwargs.setdefault("mana_cost", ManaCost.parse("{7}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Put all creature cards from all graveyards onto the battlefield "
            "under your control.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Put all creature cards from all graveyards onto the battlefield."""
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        # Collect all creature cards from all graveyards
        creatures = []
        for player in game.players:
            gy = player.zones[Zone.GRAVEYARD]
            for card in gy.get_all():
                if CardType.CREATURE in getattr(card, "card_types", set()):
                    creatures.append(card)

        for creature in creatures:
            move_to_zone(game, creature, Zone.GRAVEYARD, Zone.BATTLEFIELD)
            creature.controller = controller
