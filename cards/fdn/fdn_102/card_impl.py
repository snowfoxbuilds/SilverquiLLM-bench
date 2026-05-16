"""Card implementation for Eager Trufflesnout."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Artifact, Creature
from engine.types import CardType, Keyword, ManaCost
from engine.events import DealsDamageTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

def _make_food_token() -> Artifact:
    """Create a Food artifact token.

    ENGINE LIMITATION: The Food token's activated ability ({2}, {T},
    Sacrifice this token: You gain 3 life) is not fully functional because
    the engine does not support sacrifice-as-cost or life-gain activated
    abilities on tokens. The token is created with correct type/subtype.
    """
    from engine.card import Artifact
    token = Artifact(name='Food', subtypes={'Food'}, rules_text='{2}, {T}, Sacrifice this artifact: You gain 3 life.')
    return token

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
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            food = _make_food_token()
            create_token(game, ctrl, food)
        game.trigger_manager.register(TriggerRegistration(event_type=DealsDamageTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
