"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — {1}{W}{W} — 3/3 — Cat Cleric.

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and black "
            "Inkling creature token with flying. Then if an opponent controls more "
            "creatures than you, this creature becomes prepared.",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False
        self.chosen_targets: list[Any] = []

    def get_targets(self, game: "GameState") -> list[Any]:
        """ETB requires targeting a player."""
        from engine.player import Player

        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Player),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_etb(self, game: "GameState") -> None:
        """ETB: target player creates a 1/1 Inkling token with flying.

        Then check if an opponent controls more creatures than controller;
        if so, become prepared.
        """
        from engine.game import create_token

        # Determine target player
        target_player = self.chosen_targets[0] if self.chosen_targets else self.controller

        # Create the 1/1 Inkling token with flying for target player
        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
            owner=target_player,
            controller=target_player,
        )
        token.is_token = True
        create_token(game, target_player, token)

        # Check prepared condition: does any opponent control more creatures than controller?
        controller = self.controller
        my_creatures = sum(
            1
            for obj in game.get_battlefield(controller).get_all()
            if CardType.CREATURE in getattr(obj, "card_types", set())
        )

        for player in game.players:
            if player is controller:
                continue
            opp_creatures = sum(
                1
                for obj in game.get_battlefield(player).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            )
            if opp_creatures > my_creatures:
                self.is_prepared = True
                break

    def cast_prepared_spell(self, game: "GameState") -> None:
        """Cast the prepared spell (Swords to Plowshares copy). Unprepares."""
        self.is_prepared = False
