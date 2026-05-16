"""Card implementation for Exemplar of Light."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost
from engine.events import GainsLifeTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class ExemplarOfLight(Creature):
    """Exemplar of Light — {2}{W}{W} — 3/3 — Angel — Flying.

    Whenever you gain life, put a +1/+1 counter on this creature.
    Whenever you put one or more +1/+1 counters on this creature, draw a
    card. This ability triggers only once each turn.

    FDN collector number 11.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Exemplar of Light')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{W}{W}'))
        kwargs.setdefault('subtypes', {'Angel'})
        kwargs.setdefault('keywords', Keyword.FLYING)
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 3)
        kwargs.setdefault('rules_text', 'Flying\nWhenever you gain life, put a +1/+1 counter on this creature.\nWhenever you put one or more +1/+1 counters on this creature, draw a card. This ability triggers only once each turn.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register life-gain → +1/+1 counter trigger and counter → draw trigger."""
        from engine.game import add_counter, draw_card
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player
        source._exemplar_drew_on_turn: int = -1

        def _gain_life_condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            return event.player is ctrl

        def _gain_life_effect(game: 'GameState') -> None:
            add_counter(game, source, '+1/+1', 1)
            if hasattr(source, '_original_plus_one_counters'):
                source._original_plus_one_counters = source.plus_one_counters
            current_turn = getattr(game, 'turn_number', 0)
            if getattr(source, '_exemplar_drew_on_turn', -1) != current_turn:
                source._exemplar_drew_on_turn = current_turn
                ctrl = getattr(source, 'controller', None)
                if ctrl is not None:
                    draw_card(game, ctrl)
        game.trigger_manager.register(TriggerRegistration(event_type=GainsLifeTriggeredEvent, condition=_gain_life_condition, effect=_gain_life_effect, source=self, controller=controller))
