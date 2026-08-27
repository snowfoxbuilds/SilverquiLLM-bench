"""Card implementation for Painful Quandary."""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, Creature, Enchantment
from engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer, SubLayer
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
from engine.events import SpellCastTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState
    from cards.registry import CardRegistry

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Check if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False

class PainfulQuandary(Enchantment):
    """Painful Quandary — {3}{B}{B} — Opponent spell = lose 5 unless discard.

    Whenever an opponent casts a spell, that player loses 5 life unless
    they discard a card.

    FDN collector number 179.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Painful Quandary')
        kwargs.setdefault('mana_cost', ManaCost.parse('{3}{B}{B}'))
        kwargs.setdefault('rules_text', 'Whenever an opponent casts a spell, that player loses 5 life unless they discard a card.')
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        pass

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import TriggerRegistration
        source = self

        def _condition(game: Any, event: dict) -> bool:
            if not _is_on_battlefield(game, source):
                return False
            spell = event.spell
            if spell is None:
                return False
            controller = source.controller
            if controller is None:
                return False
            spell_controller = getattr(spell, 'controller', None)
            return spell_controller is not controller

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            from engine.game import deal_damage
            for player in game.players:
                if player is not controller:
                    from engine.game import lose_life
                    lose_life(game, player, 5)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=SpellCastTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
