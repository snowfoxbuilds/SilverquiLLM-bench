from engine.card import *
from engine.types import *
from engine.game_state import GameState
from engine.triggers import EventType, TriggerRegistration
from engine.game import create_token

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
        source = self

        def _condition(game: GameState, data: dict) -> bool:
            return data.get("permanent") is source

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            
            inkling = Creature(
                name="Inkling",
                mana_cost=ManaCost(),
                card_types={CardType.CREATURE},
                keywords=Keyword.FLYING,
                base_power=1,
                base_toughness=1,
                owner=controller,
                controller=controller,
            )
            inkling.colors = {Color.WHITE, Color.BLACK}
            inkling.is_token = True
            create_token(game, controller, inkling)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
