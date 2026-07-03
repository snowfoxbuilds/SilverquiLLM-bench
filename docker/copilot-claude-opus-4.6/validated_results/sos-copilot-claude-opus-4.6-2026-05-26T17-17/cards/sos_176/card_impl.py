"""Card implementation for Blech, Loafing Pest."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, Supertype
from engine.events import GainsLifeTriggeredEvent

if TYPE_CHECKING:
    from engine.game_state import GameState


_QUALIFYING_TYPES = {"Pest", "Bat", "Insect", "Snake", "Spider"}


class BlechLoafingPest(Creature):
    """Blech, Loafing Pest — {1}{B}{G} — 3/4 — Legendary Creature — Pest.

    Whenever you gain life, put a +1/+1 counter on each Pest, Bat, Insect,
    Snake, and Spider you control.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Blech, Loafing Pest')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{B}{G}'))
        kwargs.setdefault('subtypes', {'Pest'})
        kwargs.setdefault('supertypes', {Supertype.LEGENDARY})
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 4)
        super().__init__(**kwargs)

    @property
    def legendary(self) -> bool:
        return Supertype.LEGENDARY in self.supertypes

    @property
    def creature_types(self) -> set[str]:
        return self.subtypes

    @creature_types.setter
    def creature_types(self, value: set[str]) -> None:
        self.subtypes = value

    def register_triggers(self, game: 'GameState') -> None:
        from engine.game import add_counter
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            return event.player is ctrl

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            bf = game.get_battlefield(ctrl)
            for obj in bf.get_all():
                creature_types = getattr(obj, 'creature_types', None) or getattr(obj, 'subtypes', set())
                if creature_types & _QUALIFYING_TYPES:
                    add_counter(game, obj, '+1/+1', 1)
                    if hasattr(obj, '_base_plus_one_counters'):
                        obj._base_plus_one_counters = obj.plus_one_counters

        game.trigger_manager.register(TriggerRegistration(
            event_type=GainsLifeTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
