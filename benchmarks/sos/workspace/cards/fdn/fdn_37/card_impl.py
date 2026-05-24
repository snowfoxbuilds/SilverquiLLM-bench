"""Card implementation for Erudite Wizard."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.engine.events import DrawsCardTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

class EruditeWizard(Creature):
    """Erudite Wizard — {2}{U} — 2/3 — Human Wizard.

    Whenever you draw your second card each turn, put a +1/+1 counter on
    this creature.

    FDN collector number 37.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Erudite Wizard')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{U}'))
        kwargs.setdefault('subtypes', {'Human', 'Wizard'})
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 3)
        kwargs.setdefault('rules_text', 'Whenever you draw your second card each turn, put a +1/+1 counter on this creature.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register draw trigger: second card drawn each turn → +1/+1 counter."""
        from benchmarks.sos.workspace.engine.game import add_counter
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player
        source._erudite_draws_this_turn: int = 0
        source._erudite_last_turn: int = -1

        def _draw_condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            if event.player is not ctrl:
                return False
            current_turn = getattr(game, 'turn_number', 0)
            if getattr(source, '_erudite_last_turn', -1) != current_turn:
                source._erudite_draws_this_turn = 0
                source._erudite_last_turn = current_turn
            source._erudite_draws_this_turn += 1
            return source._erudite_draws_this_turn == 2

        def _draw_effect(game: 'GameState') -> None:
            add_counter(game, source, '+1/+1', 1)
            if hasattr(source, '_base_plus_one_counters'):
                source._base_plus_one_counters = source.plus_one_counters
        game.trigger_manager.register(TriggerRegistration(event_type=DrawsCardTriggeredEvent, condition=_draw_condition, effect=_draw_effect, source=self, controller=controller))
