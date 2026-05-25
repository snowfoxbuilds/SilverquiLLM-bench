"""Card implementation for Stromkirk Bloodthief."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import ManaCost
from engine.events import EndStepTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class StromkirkBloodthief(Creature):
    """Stromkirk Bloodthief — {2}{B} — 2/2 — Vampire Rogue.

    At the beginning of your end step, if an opponent lost life this turn,
    put a +1/+1 counter on target Vampire you control.

    FDN collector number 185.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Stromkirk Bloodthief')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{B}'))
        kwargs.setdefault('subtypes', {'Vampire', 'Rogue'})
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'At the beginning of your end step, if an opponent lost life this turn, put a +1/+1 counter on target Vampire you control.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register end step trigger for Vampire counter."""
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
            for player in game.players:
                if player is not ctrl:
                    if getattr(player, 'life_lost_this_turn', 0) > 0:
                        return True
            return False

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            from engine.types import CardType
            bf = game.get_battlefield(ctrl)
            vampires = []
            for perm in bf.get_all():
                if CardType.CREATURE in getattr(perm, 'card_types', set()):
                    subtypes = getattr(perm, 'subtypes', set())
                    if 'Vampire' in subtypes:
                        vampires.append(perm)
            if not vampires:
                return
            try:
                target = ctrl.choose_card(vampires, 'Choose a Vampire to put a +1/+1 counter on')
            except Exception:
                target = vampires[0]
            if target is not None:
                add_counter(game, target, '+1/+1', 1)
                if hasattr(target, '_base_plus_one_counters'):
                    target._base_plus_one_counters = target.plus_one_counters
        game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
