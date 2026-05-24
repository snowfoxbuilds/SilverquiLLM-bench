"""Card implementation for Cat Collector."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Artifact, Creature
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.engine.events import GainsLifeTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

def _make_food_token() -> Artifact:
    """Create a Food artifact token.

    ENGINE LIMITATION: The Food token's activated ability ({2}, {T},
    Sacrifice this token: You gain 3 life) is not fully functional because
    the engine does not support sacrifice-as-cost or life-gain activated
    abilities on tokens. The token is created with correct type/subtype.
    """
    from benchmarks.sos.workspace.engine.card import Artifact
    token = Artifact(name='Food', subtypes={'Food'}, rules_text='{2}, {T}, Sacrifice this artifact: You gain 3 life.')
    return token

class CatCollector(Creature):
    """Cat Collector — {2}{W} — 3/2 — Human Citizen.

    When this creature enters, create a Food token.
    Whenever you gain life for the first time during each of your turns,
    create a 1/1 white Cat creature token.

    FDN collector number 4.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Cat Collector')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{W}'))
        kwargs.setdefault('subtypes', {'Human', 'Citizen'})
        kwargs.setdefault('keywords', Keyword(0))
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'When this creature enters, create a Food token.\nWhenever you gain life for the first time during each of your turns, create a 1/1 white Cat creature token.')
        super().__init__(**kwargs)

    def on_resolve(self, game: 'GameState') -> None:
        """ETB: create a Food token."""
        from benchmarks.sos.workspace.engine.game import create_token
        controller = self.controller
        if controller is None:
            return
        food = _make_food_token()
        create_token(game, controller, food)

    def register_triggers(self, game: 'GameState') -> None:
        """Register life-gain trigger: first life gain each of your turns
        creates a 1/1 Cat token."""
        from benchmarks.sos.workspace.engine.game import create_token
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player
        source._cat_collector_last_triggered_turn: int = -1

        def _gain_life_condition(game: Any, event: dict) -> bool:
            """Fire on first life gain during controller's turn."""
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            if game.active_player is not ctrl:
                return False
            if event.player is not ctrl:
                return False
            current_turn = getattr(game, 'turn_number', 0)
            if getattr(source, '_cat_collector_last_triggered_turn', -1) == current_turn:
                return False
            return True

        def _gain_life_effect(game: 'GameState') -> None:
            """Create a 1/1 white Cat creature token."""
            source._cat_collector_last_triggered_turn = getattr(game, 'turn_number', 0)
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            token = Creature(name='Cat', subtypes={'Cat'}, base_power=1, base_toughness=1)
            create_token(game, ctrl, token)
        game.trigger_manager.register(TriggerRegistration(event_type=GainsLifeTriggeredEvent, condition=_gain_life_condition, effect=_gain_life_effect, source=self, controller=controller))
