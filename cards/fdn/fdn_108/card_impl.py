"""Card implementation for Needletooth Pack."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, Zone
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class NeedletoothPack(Creature):
    """Needletooth Pack — {3}{G}{G} — 4/5 — Dinosaur.

    Morbid — At the beginning of your end step, if a creature died this
    turn, put two +1/+1 counters on target creature you control.

    FDN collector number 108.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Needletooth Pack')
        kwargs.setdefault('mana_cost', ManaCost.parse('{3}{G}{G}'))
        kwargs.setdefault('subtypes', {'Dinosaur'})
        kwargs.setdefault('base_power', 4)
        kwargs.setdefault('base_toughness', 5)
        kwargs.setdefault('rules_text', 'Morbid — At the beginning of your end step, if a creature died this turn, put two +1/+1 counters on target creature you control.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        from benchmarks.sos.workspace.engine.game import add_counter
        from benchmarks.sos.workspace.engine.player import ScriptExhaustedError
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            if game.active_player is not controller:
                return False
            return getattr(game, 'creature_died_this_turn', False)

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            bf = game.get_battlefield(ctrl)
            creatures = [obj for obj in bf.get_all() if CardType.CREATURE in getattr(obj, 'card_types', set())]
            if not creatures:
                return
            target = None
            try:
                target = ctrl.choose_card(creatures, 'creature to put +1/+1 counters on')
            except ScriptExhaustedError:
                target = creatures[0]
            if target is not None and _is_on_battlefield(game, target):
                add_counter(game, target, '+1/+1', 2)
                target._base_plus_one_counters = target.plus_one_counters
        game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
