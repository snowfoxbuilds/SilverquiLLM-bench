"""Card implementation for Wildwood Scourge."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost
from benchmarks.sos.workspace.engine.events import CounterAddedTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

class WildwoodScourge(Creature):
    """Wildwood Scourge — {X}{G} — 0/0 — Hydra.

    This creature enters with X +1/+1 counters on it.
    Whenever one or more +1/+1 counters are put on another non-Hydra
    creature you control, put a +1/+1 counter on this creature.

    FDN collector number 236.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Wildwood Scourge')
        kwargs.setdefault('mana_cost', ManaCost.parse('{X}{G}'))
        kwargs.setdefault('subtypes', {'Hydra'})
        kwargs.setdefault('base_power', 0)
        kwargs.setdefault('base_toughness', 0)
        kwargs.setdefault('rules_text', 'This creature enters with X +1/+1 counters on it.\nWhenever one or more +1/+1 counters are put on another non-Hydra creature you control, put a +1/+1 counter on this creature.')
        super().__init__(**kwargs)
        self.x_value: int = 0

    def on_resolve(self, game: 'GameState') -> None:
        """Enter with X +1/+1 counters."""
        from benchmarks.sos.workspace.engine.game import add_counter
        if self.x_value > 0:
            add_counter(game, self, '+1/+1', self.x_value)
            if hasattr(self, '_base_plus_one_counters'):
                self._base_plus_one_counters = self.plus_one_counters

    def register_triggers(self, game: 'GameState') -> None:
        """Register +1/+1 counter synergy trigger.

        Whenever one or more +1/+1 counters are put on another non-Hydra
        creature you control, put a +1/+1 counter on this creature.

        ENGINE LIMITATION: The engine does not emit a dedicated
        ``COUNTER_ADDED`` event type yet.  We register for the closest
        available event and also set a marker attribute so future engine
        work can wire this up.
        """
        from benchmarks.sos.workspace.engine.game import add_counter
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player
        source._counter_synergy = True

        def _condition(game: Any, event: dict) -> bool:
            target = event.target or event.permanent
            if target is None or target is source:
                return False
            if CardType.CREATURE not in getattr(target, 'card_types', set()):
                return False
            ctrl = getattr(source, 'controller', None)
            if getattr(target, 'controller', None) is not ctrl:
                return False
            if 'Hydra' in getattr(target, 'subtypes', set()):
                return False
            counter_type = event.counter_type
            if counter_type != '+1/+1':
                return False
            return True

        def _effect(game: 'GameState') -> None:
            add_counter(game, source, '+1/+1', 1)
        if hasattr(EventType, 'COUNTER_ADDED'):
            game.trigger_manager.register(TriggerRegistration(event_type=CounterAddedTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
