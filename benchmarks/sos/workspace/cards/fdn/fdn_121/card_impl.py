"""Card implementation for Koma, World-Eater."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import Keyword, ManaCost
from engine.events import DealsDamageTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class KomaWorldEater(Creature):
    """Koma, World-Eater — {3}{G}{G}{U}{U} — 8/12 — Legendary Serpent.

    This spell can't be countered.
    Trample, ward {4}
    Whenever Koma deals combat damage to a player, create four 3/3 blue
    Serpent creature tokens named Koma's Coil.

    FDN collector number 121.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Koma, World-Eater')
        kwargs.setdefault('mana_cost', ManaCost.parse('{3}{G}{G}{U}{U}'))
        kwargs.setdefault('subtypes', {'Serpent'})
        kwargs.setdefault('supertypes', {'Legendary'})
        kwargs.setdefault('keywords', Keyword.TRAMPLE | Keyword.WARD)
        kwargs.setdefault('base_power', 8)
        kwargs.setdefault('base_toughness', 12)
        kwargs.setdefault('rules_text', "This spell can't be countered.\nTrample, ward {4}\nWhenever Koma deals combat damage to a player, create four 3/3 blue Serpent creature tokens named Koma's Coil.")
        super().__init__(**kwargs)
        self._cant_be_countered = True

    def register_triggers(self, game: 'GameState') -> None:
        """Register combat damage trigger for Serpent token creation."""
        from engine.card import Creature as _Creature
        from engine.game import create_token
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            if event.source is not source:
                return False
            if not event.is_combat:
                return False
            target = event.target
            return hasattr(target, 'life')

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            for _ in range(4):
                token = _Creature(name="Koma's Coil", subtypes={'Serpent'}, base_power=3, base_toughness=3)
                create_token(game, ctrl, token)
        game.trigger_manager.register(TriggerRegistration(event_type=DealsDamageTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
