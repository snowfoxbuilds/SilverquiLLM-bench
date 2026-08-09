"""Card implementation for Sanguine Syphoner."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import ManaCost
from engine.events import AttacksTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class SanguineSyphoner(Creature):
    """Sanguine Syphoner — {1}{B} — 1/3 — Vampire Warlock.

    Whenever this creature attacks, each opponent loses 1 life and you
    gain 1 life.

    FDN collector number 68.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Sanguine Syphoner')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{B}'))
        kwargs.setdefault('subtypes', {'Vampire', 'Warlock'})
        kwargs.setdefault('base_power', 1)
        kwargs.setdefault('base_toughness', 3)
        kwargs.setdefault('rules_text', 'Whenever this creature attacks, each opponent loses 1 life and you gain 1 life.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register attack trigger for life drain."""
        from engine.triggers import TriggerRegistration
        source = self

        def _condition(game: Any, event: dict) -> bool:
            return event.creature is source

        def _effect(game: 'GameState') -> None:
            controller = getattr(source, 'controller', None)
            if controller is None:
                return
            for player in game.players:
                if player is not controller:
                    from engine.game import lose_life
                    lose_life(game, player, 1)
            from engine.game import gain_life
            gain_life(game, controller, 1)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
