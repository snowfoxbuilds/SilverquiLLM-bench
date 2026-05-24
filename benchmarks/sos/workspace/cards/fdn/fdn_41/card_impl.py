"""Card implementation for Homunculus Horde."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.engine.events import DrawsCardTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

class HomunculusHorde(Creature):
    """Homunculus Horde — {3}{U} — 2/2 — Homunculus.

    Whenever you draw your second card each turn, create a token that's a
    copy of this creature.

    FDN collector number 41.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Homunculus Horde')
        kwargs.setdefault('mana_cost', ManaCost.parse('{3}{U}'))
        kwargs.setdefault('subtypes', {'Homunculus'})
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', "Whenever you draw your second card each turn, create a token that's a copy of this creature.")
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register draw trigger: second card drawn each turn → create copy token."""
        from benchmarks.sos.workspace.engine.game import create_token
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player
        source._horde_draws_this_turn: int = 0
        source._horde_last_turn: int = -1

        def _draw_condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            if event.player is not ctrl:
                return False
            current_turn = getattr(game, 'turn_number', 0)
            if getattr(source, '_horde_last_turn', -1) != current_turn:
                source._horde_draws_this_turn = 0
                source._horde_last_turn = current_turn
            source._horde_draws_this_turn += 1
            return source._horde_draws_this_turn == 2

        def _draw_effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            token = Creature(name='Homunculus Horde', mana_cost=ManaCost.parse('{3}{U}'), subtypes={'Homunculus'}, base_power=2, base_toughness=2)
            create_token(game, ctrl, token)
        game.trigger_manager.register(TriggerRegistration(event_type=DrawsCardTriggeredEvent, condition=_draw_condition, effect=_draw_effect, source=self, controller=controller))
