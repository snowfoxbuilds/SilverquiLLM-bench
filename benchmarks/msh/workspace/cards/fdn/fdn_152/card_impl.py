"""Card implementation for Brineborn Cutthroat."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import Keyword, ManaCost
from engine.events import SpellCastTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class BrinebornCutthroat(Creature):
    """Brineborn Cutthroat — {1}{U} — 2/1 — Merfolk Pirate — Flash.

    Whenever you cast a spell during an opponent's turn, put a +1/+1
    counter on this creature.

    FDN collector number 152.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Brineborn Cutthroat')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{U}'))
        kwargs.setdefault('subtypes', {'Merfolk', 'Pirate'})
        kwargs.setdefault('keywords', Keyword.FLASH)
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 1)
        kwargs.setdefault('rules_text', "Flash\nWhenever you cast a spell during an opponent's turn, put a +1/+1 counter on this creature.")
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register spell-cast trigger during opponent's turn."""
        from engine.game import add_counter
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            caster = event.player or event.controller
            if caster is not ctrl:
                return False
            if game.active_player is ctrl:
                return False
            return True

        def _effect(game: 'GameState') -> None:
            add_counter(game, source, '+1/+1', 1)
        game.trigger_manager.register(TriggerRegistration(event_type=SpellCastTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
