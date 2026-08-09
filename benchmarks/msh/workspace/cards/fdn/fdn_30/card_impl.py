"""Card implementation for Archmage of Runes."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.events import SpellCastTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState

class ArchmageOfRunes(Creature):
    """Archmage of Runes — {3}{U}{U} — 3/6 — Giant Wizard.

    Instant and sorcery spells you cast cost {1} less to cast.
    Whenever you cast an instant or sorcery spell, draw a card.

    FDN collector number 30.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Archmage of Runes')
        kwargs.setdefault('mana_cost', ManaCost.parse('{3}{U}{U}'))
        kwargs.setdefault('subtypes', {'Giant', 'Wizard'})
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 6)
        kwargs.setdefault('rules_text', 'Instant and sorcery spells you cast cost {1} less to cast.\nWhenever you cast an instant or sorcery spell, draw a card.')
        super().__init__(**kwargs)

    def spell_cost_reduction(self, game: 'GameState', spell: Any, caster: Any) -> int:
        """Instant/sorcery spells the controller casts cost {1} less."""
        if self.controller is not caster:
            return 0
        types = getattr(spell, 'card_types', set())
        if CardType.INSTANT in types or CardType.SORCERY in types:
            return 1
        return 0

    def register_triggers(self, game: 'GameState') -> None:
        """Register spell-cast trigger: draw a card when you cast instant/sorcery."""
        from engine.game import draw_card
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _spell_cast_condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            if event.player is not ctrl:
                return False
            spell = event.spell
            if spell is None:
                return False
            card_types = getattr(spell, 'card_types', set())
            return CardType.INSTANT in card_types or CardType.SORCERY in card_types

        def _spell_cast_effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            draw_card(game, ctrl)
        game.trigger_manager.register(TriggerRegistration(event_type=SpellCastTriggeredEvent, condition=_spell_cast_condition, effect=_spell_cast_effect, source=self, controller=controller))
