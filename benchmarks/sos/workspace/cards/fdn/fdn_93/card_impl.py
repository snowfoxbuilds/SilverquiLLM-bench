"""Card implementation for Searslicer Goblin."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

class SearslicerGoblin(Creature):
    """Searslicer Goblin — {1}{R} — 2/1 — Goblin Warrior.

    Raid — At the beginning of your end step, if you attacked this turn,
    create a 1/1 red Goblin creature token.

    FDN collector number 93.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Searslicer Goblin')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{R}'))
        kwargs.setdefault('subtypes', {'Goblin', 'Warrior'})
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 1)
        kwargs.setdefault('rules_text', 'Raid — At the beginning of your end step, if you attacked this turn, create a 1/1 red Goblin creature token.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register end-step Raid trigger for Goblin token creation."""
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            active = getattr(game, 'active_player', None)
            if active is not ctrl:
                return False
            attacked = getattr(game, 'attacked_this_turn', False)
            if not attacked:
                attacked = getattr(ctrl, 'attacked_this_turn', False)
            return attacked

        def _effect(game: 'GameState') -> None:
            from benchmarks.sos.workspace.engine.card import Creature as _Creature
            from benchmarks.sos.workspace.engine.game import create_token
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            token = _Creature(name='Goblin', subtypes={'Goblin'}, base_power=1, base_toughness=1)
            create_token(game, ctrl, token)
        game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
