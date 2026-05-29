"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import Color, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and black "
            "Inkling creature token with flying. Then if an opponent controls more "
            "creatures than you, this creature becomes prepared.",
        )
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)
        self.prepared: bool = False
        self.colors = {Color.WHITE}

    def register_triggers(self, game: "GameState") -> None:
        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: "GameState", event: EntersBattlefieldTriggeredEvent) -> bool:
            return event.permanent is source

        def _create_stack_object(
            game: "GameState",
            event: EntersBattlefieldTriggeredEvent,
            trigger: TriggerRegistration,
        ) -> StackObject | None:
            locked_controller = trigger.controller
            if locked_controller is None:
                return None

            players = list(game.players)
            try:
                chosen_player = locked_controller.choose_target(players, "player")
            except Exception:
                chosen_player = players[0] if players else None

            if chosen_player not in players:
                return None

            def _resolve(game: "GameState") -> None:
                from engine.game import create_token

                token = Creature(
                    name="Inkling",
                    subtypes={"Inkling"},
                    keywords=Keyword.FLYING,
                    base_power=1,
                    base_toughness=1,
                )
                token.colors = {Color.WHITE, Color.BLACK}
                create_token(game, chosen_player, token)

                you_count = source._count_creatures(game, locked_controller)
                source.prepared = any(
                    source._count_creatures(game, player) > you_count
                    for player in game.players
                    if player is not locked_controller
                )

                # UNVERIFIED: (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.) — spec omits the instant face rules text and the engine has no public prepared spell-copy API

            return StackObject(
                source=source,
                controller=trigger.controller,
                targets=[chosen_player],
                on_resolve=_resolve,
            )

        def _effect(game: "GameState") -> None:
            return None

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
                stack_object_factory=_create_stack_object,
            )
        )

    @staticmethod
    def _count_creatures(game: "GameState", player: Any) -> int:
        return sum(
            1
            for permanent in game.get_battlefield(player).get_all()
            if isinstance(permanent, Creature)
        )
