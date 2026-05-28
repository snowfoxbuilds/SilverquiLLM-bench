"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _is_player(obj: Any) -> bool:
    """Return True if *obj* is a Player instance."""
    from engine.player import Player as PlayerCls
    return isinstance(obj, PlayerCls)


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares

    {1}{W}{W} Creature -- Cat Cleric -- 3/3

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.

    (While it's prepared, you may cast a copy of its spell. Doing so
    unprepares it.)

    The prepare spell is Swords to Plowshares ({W} Instant):
    Exile target creature. Its controller gains life equal to its power.

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white "
            "and black Inkling creature token with flying. Then if an "
            "opponent controls more creatures than you, this creature "
            "becomes prepared.",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    # ------------------------------------------------------------------
    # Targeting -- target player for ETB
    # ------------------------------------------------------------------

    def get_targets(self, game: GameState) -> list[Any]:
        """Return a target requirement for a player (any player)."""
        return [
            TargetRequirement(
                filter_fn=_is_player,
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    # ------------------------------------------------------------------
    # ETB trigger registration
    # ------------------------------------------------------------------

    def register_triggers(self, game: GameState) -> None:
        """Register the ETB trigger for this creature."""
        source = self

        def _condition(game: GameState, event: EntersBattlefieldTriggeredEvent) -> bool:
            """Only trigger when this creature enters the battlefield."""
            return event.permanent is source

        def _effect(game: GameState) -> None:
            """Create Inkling token and check prepared condition."""
            source.on_resolve(game)

        controller = self.controller if self.controller is not None else self.owner
        if controller is None:
            return

        trigger = TriggerRegistration(
            event_type=EntersBattlefieldTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        )
        game.trigger_manager.register(trigger)

    # ------------------------------------------------------------------
    # Resolution -- create Inkling token, check prepared condition
    # ------------------------------------------------------------------

    def on_resolve(self, game: GameState) -> None:
        """Create a 1/1 Inkling token with flying for the target player.

        Then check if any opponent controls more creatures than the
        controller. If so, this creature becomes prepared.
        """
        from engine.game import create_token

        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return

        target_player = chosen[0]
        if target_player is None:
            return

        # Verify the target is a player
        if not _is_player(target_player):
            return

        controller = self.controller if self.controller is not None else self.owner
        if controller is None:
            return

        # Create a 1/1 white and black Inkling creature token with flying
        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
            owner=target_player,
            controller=target_player,
        )
        # Set colors on the token (white and black)
        token.colors = ["W", "B"]

        create_token(game, target_player, token)

        # Check prepared condition: if any opponent controls more creatures
        # than the controller, this creature becomes prepared.
        my_creatures = self._count_creatures(game, controller)
        for player in game.players:
            if player is not controller:
                opp_creatures = self._count_creatures(game, player)
                if opp_creatures > my_creatures:
                    self.is_prepared = True
                    return

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _count_creatures(game: GameState, player: Any) -> int:
        """Count the number of creatures a player controls on the battlefield."""
        battlefield = game.get_battlefield(player)
        count = 0
        for obj in battlefield.get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                count += 1
        return count
