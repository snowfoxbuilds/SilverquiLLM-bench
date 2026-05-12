from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import *
from engine.types import *

if TYPE_CHECKING:
    from engine.game_state import GameState


class EagerGlyphmage(Creature):
    """Eager Glyphmage."""

    def __init__(self, **kwargs):
        super().__init__(
            name="Eager Glyphmage",
            mana_cost=ManaCost.parse("{3}{W}"),
            card_types={CardType.CREATURE},
            subtypes={"Cat", "Cleric"},
            rules_text="""When this creature enters, create a 1/1 white and black Inkling creature token with flying.""",
            base_power=3,
            base_toughness=3,
            **kwargs,
        )

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import create_token
        from engine.protection import Color

        source = self

        def _condition(game: GameState, data: dict) -> bool:
            return data.get("permanent") is source

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is not None:
                token = Creature(
                    name="Inkling",
                    subtypes={"Inkling"},
                    keywords=Keyword.FLYING,
                    base_power=1,
                    base_toughness=1,
                    owner=controller,
                    controller=controller,
                )
                token.colors = {Color.WHITE, Color.BLACK}
                create_token(game, controller, token)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
