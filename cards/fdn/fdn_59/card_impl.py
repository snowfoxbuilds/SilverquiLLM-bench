"""Card implementation for Crypt Feaster."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from engine.types import Keyword, ManaCost, Zone
from engine.events import AttacksTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class CryptFeaster(Creature):
    """Crypt Feaster — {3}{ 3/4 — Zombie — Menace.B} 

    Threshold — Whenever this creature attacks, if there are seven or more
    cards in your graveyard, this creature gets +2/+0 until end of turn.

    FDN collector number 59.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Crypt Feaster')
        kwargs.setdefault('mana_cost', ManaCost.parse('{3}{B}'))
        kwargs.setdefault('subtypes', {'Zombie'})
        kwargs.setdefault('keywords', Keyword.MENACE)
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 4)
        kwargs.setdefault('rules_text', 'Menace\nThreshold — Whenever this creature attacks, if there are seven or more cards in your graveyard, this creature gets +2/+0 until end of turn.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register threshold attack trigger."""
        from engine.triggers import TriggerRegistration
        source = self

        def _condition(game: Any, event: dict) -> bool:
            if event.creature is not source:
                return False
            controller = getattr(source, 'controller', None)
            if controller is None:
                return False
            gy = controller.zones[Zone.GRAVEYARD]
            return len(gy.get_all()) >= 7

        def _effect(game: 'GameState') -> None:

            def _apply(game: Any) -> None:
                source.base_power = source.base_power + 2
            game.effect_manager.add(ContinuousEffect(source=source, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT, apply=_apply, duration=DURATION_END_OF_TURN))
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
