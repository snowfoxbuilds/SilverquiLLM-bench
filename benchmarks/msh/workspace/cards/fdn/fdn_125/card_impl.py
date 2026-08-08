"""Card implementation for Wardens of the Cycle."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.card_queries import choose_mode
from engine.types import ManaCost
from engine.events import EndStepTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class WardensOfTheCycle(Creature):
    """Wardens of the Cycle — {1}{B}{G}{G} — 3/4 — Elf Warlock.

    Morbid — At the beginning of your end step, if a creature died this
    turn, choose one —
    • You gain 2 life.
    • You draw a card and you lose 1 life.

    FDN collector number 125.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Wardens of the Cycle')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{B}{G}{G}'))
        kwargs.setdefault('subtypes', {'Elf', 'Warlock'})
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 4)
        kwargs.setdefault('rules_text', 'Morbid — At the beginning of your end step, if a creature died this turn, choose one —\n• You gain 2 life.\n• You draw a card and you lose 1 life.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register Morbid end-step trigger."""
        from engine.game import draw_card
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            if game.active_player is not ctrl:
                return False
            return getattr(game, 'creature_died_this_turn', False)

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            mode = choose_mode(game, ctrl, ['gain_life', 'draw_card'], 'Choose: gain 2 life or draw a card and lose 1 life', source_card=source)
            if mode == 'draw_card':
                draw_card(game, ctrl)
                from engine.game import lose_life
                lose_life(game, ctrl, 1)
            else:
                from engine.game import gain_life
                gain_life(game, ctrl, 2)
        game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
