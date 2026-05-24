"""Card implementation for Good-Fortune Unicorn."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from collections import deque
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

class GoodFortuneUnicorn(Creature):
    """Good-Fortune Unicorn — {1}{G}{W} — 2/2 — Unicorn.

    Whenever another creature you control enters, put a +1/+1 counter
    on that creature.

    FDN collector number 240.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Good-Fortune Unicorn')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{G}{W}'))
        kwargs.setdefault('subtypes', {'Unicorn'})
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'Whenever another creature you control enters, put a +1/+1 counter on that creature.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register ETB trigger for other creatures."""
        from benchmarks.sos.workspace.engine.game import add_counter
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player
        _queue: deque = deque()

        def _condition(game: Any, event: dict) -> bool:
            permanent = event.permanent
            if permanent is None or permanent is source:
                return False
            ctrl = getattr(source, 'controller', None)
            if getattr(permanent, 'controller', None) is not ctrl:
                return False
            if CardType.CREATURE not in getattr(permanent, 'card_types', set()):
                return False
            _queue.append(permanent)
            return True

        def _effect(game: 'GameState') -> None:
            if not _queue:
                return
            target = _queue.popleft()
            add_counter(game, target, '+1/+1', 1)
            if hasattr(target, '_base_plus_one_counters'):
                target._base_plus_one_counters = target.plus_one_counters
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
