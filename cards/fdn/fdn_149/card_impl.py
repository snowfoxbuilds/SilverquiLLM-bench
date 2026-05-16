"""Card implementation for Youthful Valkyrie."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import Keyword, ManaCost
from engine.events import EntersBattlefieldTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class YouthfulValkyrie(Creature):
    """Youthful Valkyrie — {1}{W} — 1/3 — Angel — Flying.

    Whenever another Angel you control enters, put a +1/+1 counter on
    this creature.

    FDN collector number 149.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Youthful Valkyrie')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{W}'))
        kwargs.setdefault('subtypes', {'Angel'})
        kwargs.setdefault('keywords', Keyword.FLYING)
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 3)
        kwargs.setdefault('rules_text', 'Flying\nWhenever another Angel you control enters, put a +1/+1 counter on this creature.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register trigger: another Angel ETB → +1/+1 counter."""
        from engine.game import add_counter
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            permanent = event.permanent
            if permanent is None or permanent is source:
                return False
            ctrl = getattr(source, 'controller', None)
            if getattr(permanent, 'controller', None) is not ctrl:
                return False
            if 'Angel' not in getattr(permanent, 'subtypes', set()):
                return False
            return True

        def _effect(game: 'GameState') -> None:
            add_counter(game, source, '+1/+1', 1)
            if hasattr(source, '_original_plus_one_counters'):
                source._original_plus_one_counters = source.plus_one_counters
        game.trigger_manager.register(TriggerRegistration(event_type=EntersBattlefieldTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
