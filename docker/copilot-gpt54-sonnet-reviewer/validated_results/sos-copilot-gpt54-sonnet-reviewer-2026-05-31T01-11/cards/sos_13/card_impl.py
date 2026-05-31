"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.game import create_token
from engine.stack import StackObject
from engine.triggers import TriggerRegistration
from engine.types import CardType, Color, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _count_creatures(game: "GameState", player: "Player") -> int:
    """Count creatures that player currently controls on the battlefield."""
    return sum(
        1
        for permanent in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(permanent, "card_types", set())
    )


def _make_inkling_token() -> Creature:
    """Create the 1/1 white and black Inkling token for the ETB trigger."""
    token = Creature(
        name="Inkling",
        subtypes={"Inkling"},
        keywords=Keyword.FLYING,
        base_power=1,
        base_toughness=1,
    )
    token.colors = {Color.WHITE, Color.BLACK}
    return token


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and black Inkling creature "
            "token with flying. Then if an opponent controls more creatures than you, this creature "
            "becomes prepared. (While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    def register_triggers(self, game: "GameState") -> None:
        source = self
        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.unregister(source)

        def _condition(game: "GameState", event: EntersBattlefieldTriggeredEvent) -> bool:
            return event.permanent is source

        def _build_stack_object(
            game: "GameState",
            event: EntersBattlefieldTriggeredEvent,
        ) -> StackObject | None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None or event.permanent is not source:
                return None

            chosen_player = ctrl.choose_target(list(game.players), "target player")
            if chosen_player not in game.players:
                return None

            def _resolve_trigger(game: "GameState") -> None:
                create_token(game, chosen_player, _make_inkling_token())

                source_controller = getattr(source, "controller", None)
                if source_controller is None:
                    return
                your_creatures = _count_creatures(game, source_controller)
                for player in game.players:
                    if player is source_controller:
                        continue
                    if _count_creatures(game, player) > your_creatures:
                        source.is_prepared = True
                        return

            return StackObject(
                source=source,
                controller=ctrl,
                targets=[chosen_player],
                on_resolve=_resolve_trigger,
            )

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_condition,
                effect=lambda _game: None,
                source=source,
                controller=controller,
                stack_builder=_build_stack_object,
            )
        )
