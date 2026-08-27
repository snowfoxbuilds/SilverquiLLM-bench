"""Card implementation for Nessian Hornbeetle."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.events import BeginningOfCombatTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class NessianHornbeetle(Creature):
    """Nessian Hornbeetle — {1}{G} — 2/2 — Insect.

    At the beginning of combat on your turn, if you control another
    creature with power 4 or greater, put a +1/+1 counter on this
    creature.

    FDN collector number 229.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Nessian Hornbeetle')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{G}'))
        kwargs.setdefault('subtypes', {'Insect'})
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'At the beginning of combat on your turn, if you control another creature with power 4 or greater, put a +1/+1 counter on this creature.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register beginning of combat trigger."""
        from engine.game import add_counter
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            if game.active_player is not ctrl:
                return False
            bf = game.get_battlefield(ctrl)
            for obj in bf.get_all():
                if obj is source:
                    continue
                if CardType.CREATURE not in getattr(obj, 'card_types', set()):
                    continue
                power = getattr(obj, 'power', getattr(obj, 'base_power', 0))
                if power >= 4:
                    return True
            return False

        def _effect(game: 'GameState') -> None:
            add_counter(game, source, '+1/+1', 1)
        game.trigger_manager.register(TriggerRegistration(event_type=BeginningOfCombatTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
