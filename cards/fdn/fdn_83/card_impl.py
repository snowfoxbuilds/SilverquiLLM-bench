"""Card implementation for Crackling Cyclops."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.continuous_effects import ContinuousEffect, DURATION_END_OF_TURN, Layer, SubLayer
from engine.types import CardType, ManaCost
from engine.events import SpellCastTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class CracklingCyclops(Creature):
    """Crackling Cyclops — {2}{R} — 0/4 — Cyclops Wizard.

    Whenever you cast a noncreature spell, this creature gets +3/+0
    until end of turn.

    FDN collector number 83.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Crackling Cyclops')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{R}'))
        kwargs.setdefault('subtypes', {'Cyclops', 'Wizard'})
        kwargs.setdefault('base_power', 0)
        kwargs.setdefault('base_toughness', 4)
        kwargs.setdefault('rules_text', 'Whenever you cast a noncreature spell, this creature gets +3/+0 until end of turn.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register spell-cast trigger for +3/+0."""
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            spell = event.spell
            caster = event.player
            ctrl = getattr(source, 'controller', None)
            if caster is not ctrl:
                return False
            card_types = getattr(spell, 'card_types', set())
            return CardType.CREATURE not in card_types

        def _effect(game: 'GameState') -> None:

            def _apply(game: Any) -> None:
                source.base_power += 3
            game.effect_manager.add(ContinuousEffect(source=source, layer=Layer.POWER_TOUGHNESS, sublayer=SubLayer.MODIFY_PT, apply=_apply, duration=DURATION_END_OF_TURN))
        game.trigger_manager.register(TriggerRegistration(event_type=SpellCastTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
