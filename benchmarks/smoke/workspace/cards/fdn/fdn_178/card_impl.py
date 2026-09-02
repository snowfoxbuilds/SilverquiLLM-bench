"""Card implementation for Marauding Blight-Priest."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import ManaCost
from engine.events import GainsLifeTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class MaraudingBlightPriest(Creature):
    """Marauding Blight-Priest — {2}{B} — 3/2 — Vampire Cleric.

    Whenever you gain life, each opponent loses 1 life.

    FDN collector number 178.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Marauding Blight-Priest')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{B}'))
        kwargs.setdefault('subtypes', {'Vampire', 'Cleric'})
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'Whenever you gain life, each opponent loses 1 life.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register life-gain trigger to drain opponents."""
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            return event.player is ctrl

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            for player in game.players:
                if player is not ctrl:
                    from engine.game import lose_life
                    lose_life(game, player, 1)
        game.trigger_manager.register(TriggerRegistration(event_type=GainsLifeTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
