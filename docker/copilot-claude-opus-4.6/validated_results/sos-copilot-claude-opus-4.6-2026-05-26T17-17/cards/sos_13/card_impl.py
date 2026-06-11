"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 — Cat Cleric.

    ETB: target player creates a 1/1 W/B Inkling token with flying.
    Then if an opponent controls more creatures than you, this creature
    becomes prepared.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """ETB: create Inkling for target player, then check prepared condition."""
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Determine target player for the token
        chosen = getattr(self, "chosen_targets", None)
        target_player = chosen[0] if chosen else controller

        # Create 1/1 W/B Inkling with flying for target player
        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            base_power=1,
            base_toughness=1,
            keywords=Keyword.FLYING,
        )
        create_token(game, target_player, token)

        # Check if an opponent controls more creatures than controller
        my_creatures = len([
            obj for obj in game.get_battlefield(controller).get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        ])

        for player in game.players:
            if player is controller:
                continue
            opp_creatures = len([
                obj for obj in game.get_battlefield(player).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            ])
            if opp_creatures > my_creatures:
                self.is_prepared = True
                break

    def can_cast_prepared(self, game: "GameState") -> bool:
        """Return True if the prepared spell can be cast."""
        return self.is_prepared

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast a copy of Swords to Plowshares and unprepare."""
        if not self.is_prepared:
            return
        self.is_prepared = False
