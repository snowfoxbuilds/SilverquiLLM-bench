"""Card implementation for Dragon Trainer."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ArtifactCreature, Creature
from benchmarks.sos.workspace.engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.cards.registry import CardRegistry

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
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        from benchmarks.sos.workspace.engine.game import create_token
        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, 'controller', None)
            if controller is not None:
                token = Creature(name='Dragon', subtypes={'Dragon'}, keywords=Keyword.FLYING, base_power=4, base_toughness=4, owner=controller, controller=controller)
                create_token(game, controller, token)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_self_etb_condition(self), effect=_effect, source=self, controller=controller))
