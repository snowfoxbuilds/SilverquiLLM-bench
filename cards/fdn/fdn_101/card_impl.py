"""Card implementation for Cackling Prowler."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import Keyword, ManaCost
from engine.events import EndStepTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class CacklingProwler(Creature):
    """Cackling Prowler — {3}{G} — 4/3 — Hyena Rogue — Ward {2}.

    Morbid — At the beginning of your end step, if a creature died this
    turn, put a +1/+1 counter on this creature.

    FDN collector number 101.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Cackling Prowler')
        kwargs.setdefault('mana_cost', ManaCost.parse('{3}{G}'))
        kwargs.setdefault('subtypes', {'Hyena', 'Rogue'})
        kwargs.setdefault('keywords', Keyword.WARD)
        kwargs.setdefault('base_power', 4)
        kwargs.setdefault('base_toughness', 3)
        kwargs.setdefault('rules_text', 'Ward {2}\nMorbid — At the beginning of your end step, if a creature died this turn, put a +1/+1 counter on this creature.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        from engine.game import add_counter
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            if game.active_player is not controller:
                return False
            return getattr(game, 'creature_died_this_turn', False)

        def _effect(game: 'GameState') -> None:
            add_counter(game, source, '+1/+1')
            source._original_plus_one_counters = source.plus_one_counters
        game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
