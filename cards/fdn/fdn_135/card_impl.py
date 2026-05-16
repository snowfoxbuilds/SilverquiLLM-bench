"""Card implementation for Ajani's Pridemate."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import ManaCost
from engine.events import GainsLifeTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class AjanisPridemate(Creature):
    """Ajani's Pridemate — {1}{W} — 2/2 — Cat Soldier.

    Whenever you gain life, put a +1/+1 counter on this creature.

    FDN collector number 135.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', "Ajani's Pridemate")
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{W}'))
        kwargs.setdefault('subtypes', {'Cat', 'Soldier'})
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'Whenever you gain life, put a +1/+1 counter on this creature.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register life-gain → +1/+1 counter trigger."""
        from engine.game import add_counter
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            return event.player is ctrl

        def _effect(game: 'GameState') -> None:
            add_counter(game, source, '+1/+1', 1)
            if hasattr(source, '_base_plus_one_counters'):
                source._base_plus_one_counters = source.plus_one_counters
        game.trigger_manager.register(TriggerRegistration(event_type=GainsLifeTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
