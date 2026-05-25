"""Card implementation for Sylvan Scavenging."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature, Enchantment
from engine.types import CardType, ManaCost, Zone
from engine.events import EndStepTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class SylvanScavenging(Enchantment):
    """Sylvan Scavenging — {1}{G}{G} — Enchantment.

    At the beginning of your end step, choose one —
    • Put a +1/+1 counter on target creature you control.
    • Create a 3/3 green Raccoon creature token if you control a creature
      with power 4 or greater.

    FDN collector number 113.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Sylvan Scavenging')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{G}{G}'))
        kwargs.setdefault('rules_text', 'At the beginning of your end step, choose one —\n• Put a +1/+1 counter on target creature you control.\n• Create a 3/3 green Raccoon creature token if you control a creature with power 4 or greater.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        from engine.game import add_counter, create_token
        from engine.player import ScriptExhaustedError
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            return game.active_player is controller

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            if not _is_on_battlefield(game, source):
                return
            bf = game.get_battlefield(ctrl)
            creatures = [obj for obj in bf.get_all() if CardType.CREATURE in getattr(obj, 'card_types', set())]
            has_power_4 = any((getattr(c, 'power', getattr(c, 'base_power', 0)) >= 4 for c in creatures))
            modes = []
            if creatures:
                modes.append('counter')
            if has_power_4:
                modes.append('token')
            if not modes:
                return
            chosen_mode = None
            if len(modes) == 1:
                chosen_mode = modes[0]
            else:
                try:
                    chosen_mode = ctrl.choose_card(modes, 'choose mode: counter or token')
                except ScriptExhaustedError:
                    chosen_mode = modes[0]
            if chosen_mode == 'counter' and creatures:
                target = None
                try:
                    target = ctrl.choose_card(creatures, 'creature to put +1/+1 counter on')
                except ScriptExhaustedError:
                    target = creatures[0]
                if target is not None and _is_on_battlefield(game, target):
                    add_counter(game, target, '+1/+1')
                    target._base_plus_one_counters = target.plus_one_counters
            elif chosen_mode == 'token' and has_power_4:
                token = Creature(name='Raccoon', subtypes={'Raccoon'}, base_power=3, base_toughness=3, rules_text='')
                create_token(game, ctrl, token)
        game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
