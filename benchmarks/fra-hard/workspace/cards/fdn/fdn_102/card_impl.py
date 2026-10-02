"""Card implementation for Eager Trufflesnout."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import Keyword, ManaCost
from engine.events import DealsDamageTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class EagerTrufflesnout(Creature):
    """Eager Trufflesnout — {2}{G} — 4/2 — Boar — Trample.

    Whenever this creature deals combat damage to a player, create a
    Food token.

    FDN collector number 102.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Eager Trufflesnout')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{G}'))
        kwargs.setdefault('subtypes', {'Boar'})
        kwargs.setdefault('keywords', Keyword.TRAMPLE)
        kwargs.setdefault('base_power', 4)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'Trample\nWhenever this creature deals combat damage to a player, create a Food token.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        from engine.game import create_token
        from engine.player import Player
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            if event.source is not source:
                return False
            if not event.is_combat:
                return False
            target = event.target
            return isinstance(target, Player)

        def _effect(game: 'GameState') -> None:
            from cards.fdn.tokens import make_food_token
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            create_token(game, ctrl, make_food_token())
        game.trigger_manager.register(TriggerRegistration(event_type=DealsDamageTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
