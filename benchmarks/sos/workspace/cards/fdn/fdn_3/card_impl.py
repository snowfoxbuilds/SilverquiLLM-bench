"""Card implementation for Armasaur Guide."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost
from engine.events import AttacksTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class ArmasaurGuide(Creature):
    """Armasaur Guide — {4}{W} — 4/4 — Dinosaur — Vigilance.

    Whenever you attack with three or more creatures, put a +1/+1 counter
    on target creature you control.

    FDN collector number 3.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Armasaur Guide')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{W}'))
        kwargs.setdefault('subtypes', {'Dinosaur'})
        kwargs.setdefault('keywords', Keyword.VIGILANCE)
        kwargs.setdefault('base_power', 4)
        kwargs.setdefault('base_toughness', 4)
        kwargs.setdefault('rules_text', 'Vigilance\nWhenever you attack with three or more creatures, put a +1/+1 counter on target creature you control.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register attack trigger: 3+ attackers → +1/+1 counter on target."""
        from engine.game import add_counter
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _attack_condition(game: Any, event: dict) -> bool:
            """Fire when controller attacks with 3+ creatures."""
            attacker = event.creature
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            battlefield = game.get_battlefield(ctrl)
            attacking = [c for c in battlefield.get_all() if CardType.CREATURE in getattr(c, 'card_types', set()) and getattr(c, 'is_attacking', False)]
            return len(attacking) >= 3 and attacker is source

        def _attack_effect(game: 'GameState') -> None:
            """Put a +1/+1 counter on target creature you control."""
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            chosen = getattr(source, 'chosen_targets', None)
            if chosen:
                target = chosen[0]
            else:
                battlefield = game.get_battlefield(ctrl)
                candidates = [c for c in battlefield.get_all() if CardType.CREATURE in getattr(c, 'card_types', set())]
                if not candidates:
                    return
                try:
                    target = ctrl.choose_card(candidates, 'target creature for +1/+1 counter')
                except Exception:
                    target = candidates[0]
            if target is None:
                return
            add_counter(game, target, '+1/+1', 1)
            if hasattr(target, '_base_plus_one_counters'):
                target._base_plus_one_counters = target.plus_one_counters
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_attack_condition, effect=_attack_effect, source=self, controller=controller))
