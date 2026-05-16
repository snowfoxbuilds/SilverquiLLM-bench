"""Card implementation for Courageous Goblin."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from engine.types import CardType, Keyword, ManaCost
from engine.events import AttacksTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class CourageousGoblin(Creature):
    """Courageous Goblin — {1}{R} — 2/2 — Goblin.

    Whenever this creature attacks while you control a creature with power
    4 or greater, this creature gets +1/+0 and gains menace until end of turn.

    FDN collector number 82.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Courageous Goblin')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{R}'))
        kwargs.setdefault('subtypes', {'Goblin'})
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'Whenever this creature attacks while you control a creature with power 4 or greater, this creature gets +1/+0 and gains menace until end of turn.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register conditional attack trigger."""
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            if event.creature is not source:
                return False
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            bf = game.get_battlefield(ctrl)
            for obj in bf.get_all():
                if CardType.CREATURE not in getattr(obj, 'card_types', set()):
                    continue
                if getattr(obj, 'power', getattr(obj, 'base_power', 0)) >= 4:
                    return True
            return False

        def _effect(game: 'GameState') -> None:

            def _apply(game: Any) -> None:
                source.base_power += 1
                source.keywords = (getattr(source, 'keywords', None) or Keyword(0)) | Keyword.MENACE
            game.effect_manager.add(ContinuousEffect(source=source, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT, apply=_apply, duration=DURATION_END_OF_TURN))
        game.trigger_manager.register(TriggerRegistration(event_type=AttacksTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
