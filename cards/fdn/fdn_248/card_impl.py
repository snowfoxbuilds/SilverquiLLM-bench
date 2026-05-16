"""Card implementation for Thousand-Year Storm."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Enchantment
from engine.types import CardType, ManaCost
from engine.events import SpellCastTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class ThousandYearStorm(Enchantment):
    """Thousand-Year Storm — {4}{U}{R} — Enchantment.

    Whenever you cast an instant or sorcery spell, copy it for each
    other instant and sorcery spell you've cast before it this turn.
    You may choose new targets for the copies.

    FDN collector number 248.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Thousand-Year Storm')
        kwargs.setdefault('mana_cost', ManaCost.parse('{4}{U}{R}'))
        kwargs.setdefault('rules_text', "Whenever you cast an instant or sorcery spell, copy it for each other instant and sorcery spell you've cast before it this turn. You may choose new targets for the copies.")
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register spell-copy trigger."""
        from engine.stack import StackObject
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player
        prior_count = 0
        current_turn = getattr(game, 'turn_number', 0)
        if hasattr(game, 'spells_cast_this_turn'):
            for entry in game.spells_cast_this_turn:
                card = entry.get('card') or entry.get('spell')
                caster = entry.get('player') or entry.get('controller')
                if caster is not controller:
                    continue
                card_types = getattr(card, 'card_types', set())
                if card_types & {CardType.INSTANT, CardType.SORCERY}:
                    prior_count += 1
        source._storm_count: int = prior_count
        source._last_turn: int = current_turn

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            caster = event.player or event.controller
            if caster is not ctrl:
                return False
            spell = event.card or event.spell
            if spell is None:
                return False
            card_types = getattr(spell, 'card_types', set())
            if not card_types & {CardType.INSTANT, CardType.SORCERY}:
                return False
            current_turn = getattr(game, 'turn_number', 0)
            if current_turn != source._last_turn:
                source._storm_count = 0
                source._last_turn = current_turn
            return True

        def _effect(game: 'GameState') -> None:
            copies_to_make = source._storm_count
            source._storm_count += 1
            if copies_to_make <= 0:
                return
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            stack_items = list(game.stack._objects) if hasattr(game.stack, '_objects') else []
            if not stack_items:
                return
            original = stack_items[-1] if stack_items else None
            if original is None:
                return
            for _ in range(copies_to_make):
                copy_obj = StackObject(source=original.source, controller=ctrl, on_resolve=original.on_resolve, targets=list(original.targets) if original.targets else [])
                game.stack.push(copy_obj)
        game.trigger_manager.register(TriggerRegistration(event_type=SpellCastTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
