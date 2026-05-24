"""Card implementation for Resolute Reinforcements."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import ArtifactCreature, Creature
from benchmarks.sos.workspace.engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, Zone
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from cards.registry import CardRegistry

def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, event: dict) -> bool:
        return event.permanent is source
    return _condition

class ResoluteReinforcements(Creature):
    """Resolute Reinforcements — {1}{W} — 1/1 — Human Soldier — Flash

    When this creature enters, create a 1/1 white Soldier creature token.

    FDN collector number 145.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Resolute Reinforcements')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{W}'))
        kwargs.setdefault('subtypes', {'Human', 'Soldier'})
        kwargs.setdefault('keywords', Keyword.FLASH)
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 1)
        kwargs.setdefault('rules_text', 'Flash\nWhen this creature enters, create a 1/1 white Soldier creature token.')
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        from benchmarks.sos.workspace.engine.game import create_token
        source = self

        def _effect(game: GameState) -> None:
            controller = getattr(source, 'controller', None)
            if controller is not None:
                token = Creature(name='Soldier', subtypes={'Human', 'Soldier'}, base_power=1, base_toughness=1, owner=controller, controller=controller)
                create_token(game, controller, token)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_self_etb_condition(self), effect=_effect, source=self, controller=controller))
