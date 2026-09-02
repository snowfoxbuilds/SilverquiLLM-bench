"""Card implementation for Dragon Trainer."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ArtifactCreature, Creature
from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from engine.types import CardType, Color, Keyword, ManaCost, Zone
from engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState
    from cards.registry import CardRegistry

def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, event: dict) -> bool:
        return event.permanent is source
    return _condition

class DragonTrainer(Creature):
    """Dragon Trainer — {3}{R}{R} — 1/1 — Human

    When this creature enters, create a 4/4 red Dragon creature token with flying.

    FDN collector number 84.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Dragon Trainer')
        kwargs.setdefault('mana_cost', ManaCost.parse('{3}{R}{R}'))
        kwargs.setdefault('subtypes', {'Human'})
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 1)
        kwargs.setdefault('rules_text', 'When this creature enters, create a 4/4 red Dragon creature token with flying.')
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import TriggerRegistration
        from engine.game import create_token
        source = self

        def _effect(game: GameState) -> None:
            from cards.fdn.tokens import make_creature_token
            controller = getattr(source, 'controller', None)
            if controller is not None:
                token = make_creature_token(
                    'Dragon', {'Dragon'}, [Color.RED], 4, 4, keywords=Keyword.FLYING
                )
                create_token(game, controller, token)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_self_etb_condition(self), effect=_effect, source=self, controller=controller))
