"""Card implementation for Rite of the Dragoncaller."""
from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from cards.fdn.tokens import make_creature_token
from engine.card import ActivatedAbility, Enchantment
from engine.continuous_effects import ContinuousEffect, DURATION_PERMANENT, Layer, SubLayer
from engine.types import CardType, Color, Keyword, ManaCost, TargetRequirement, Zone
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

class RiteOfTheDragoncaller(Enchantment):
    """Rite of the Dragoncaller — {4}{R}{R} — Create 5/5 Dragon on spell cast.

    Whenever you cast an instant or sorcery spell, create a 5/5 red Dragon
    creature token with flying.

    FDN collector number 92.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Rite of the Dragoncaller')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{R}{R}'))
        kwargs.setdefault('rules_text', 'Whenever you cast an instant or sorcery spell, create a 5/5 red Dragon creature token with flying.')
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        pass

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import TriggerRegistration
        from engine.game import create_token
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
            if spell_controller is not controller:
                return False
            card_types = getattr(spell, 'card_types', set())
            return CardType.INSTANT in card_types or CardType.SORCERY in card_types

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            token = make_creature_token("Dragon", {"Dragon"}, [Color.RED], 5, 5, keywords=Keyword.FLYING)
            create_token(game, controller, token)
        controller = getattr(self, 'controller', None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(event_type=SpellCastTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
