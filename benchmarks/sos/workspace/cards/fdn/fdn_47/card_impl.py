"""Card implementation for Mischievous Mystic."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import Keyword, ManaCost
from engine.events import DrawsCardTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class MischievousMystic(Creature):
    """Mischievous Mystic — {1}{U} — 2/1 — Human Wizard — Flying.

    Whenever you draw your second card each turn, create a 1/1 blue Faerie
    creature token with flying.

    FDN collector number 47.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Mischievous Mystic')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{U}'))
        kwargs.setdefault('subtypes', {'Human', 'Wizard'})
        kwargs.setdefault('keywords', Keyword.FLYING)
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 1)
        kwargs.setdefault('rules_text', 'Flying\nWhenever you draw your second card each turn, create a 1/1 blue Faerie creature token with flying.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register draw trigger: second card each turn → Faerie token."""
        from engine.game import create_token
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player
        source._mystic_draws_this_turn: int = 0
        source._mystic_last_turn: int = -1

        def _draw_condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            if event.player is not ctrl:
                return False
            current_turn = getattr(game, 'turn_number', 0)
            if getattr(source, '_mystic_last_turn', -1) != current_turn:
                source._mystic_draws_this_turn = 0
                source._mystic_last_turn = current_turn
            source._mystic_draws_this_turn += 1
            return source._mystic_draws_this_turn == 2

        def _draw_effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            token = Creature(name='Faerie', subtypes={'Faerie'}, keywords=Keyword.FLYING, base_power=1, base_toughness=1)
            create_token(game, ctrl, token)
        game.trigger_manager.register(TriggerRegistration(event_type=DrawsCardTriggeredEvent, condition=_draw_condition, effect=_draw_effect, source=self, controller=controller))
