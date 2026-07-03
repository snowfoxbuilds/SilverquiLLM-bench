"""Card implementation for Colorstorm Stallion."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import Keyword, ManaCost, CardType
from engine.events import SpellCastTriggeredEvent

if TYPE_CHECKING:
    from engine.game_state import GameState


class ColorstormStallion(Creature):
    """Colorstorm Stallion — {1}{U}{R} — 3/3 — Elemental Horse.

    Ward {1}, haste
    Opus — Whenever you cast an instant or sorcery spell, this creature gets
    +1/+1 until end of turn. If five or more mana was spent to cast that spell,
    create a token that's a copy of this creature.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Colorstorm Stallion')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{U}{R}'))
        kwargs.setdefault('subtypes', {'Elemental', 'Horse'})
        kwargs.setdefault('keywords', Keyword.WARD | Keyword.HASTE)
        kwargs.setdefault('base_power', 3)
        kwargs.setdefault('base_toughness', 3)
        super().__init__(**kwargs)
        self._temp_power_bonus: int = 0
        self._temp_toughness_bonus: int = 0

    @property
    def power(self) -> int:
        return self.modified_power + self.plus_one_counters - self.minus_one_counters + self._temp_power_bonus

    @property
    def toughness(self) -> int:
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters + self._temp_toughness_bonus

    def register_triggers(self, game: 'GameState') -> None:
        from engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: Any) -> bool:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return False
            # Must be cast by the controller
            caster = getattr(event, 'player', None) or getattr(event, 'controller', None)
            if caster is not ctrl:
                return False
            # Must be an instant or sorcery
            spell = getattr(event, 'spell', None) or getattr(event, 'card', None)
            if spell is None:
                return False
            card_types = getattr(spell, 'card_types', set())
            return CardType.INSTANT in card_types or CardType.SORCERY in card_types

        def _effect(game: 'GameState') -> None:
            # Give +1/+1 until end of turn
            source._temp_power_bonus = getattr(source, '_temp_power_bonus', 0) + 1
            source._temp_toughness_bonus = getattr(source, '_temp_toughness_bonus', 0) + 1

        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))

    def on_spell_cast(self, game: 'GameState', event: Any) -> None:
        """Handle opus trigger for 5+ mana spells — create token copy."""
        ctrl = getattr(self, 'controller', None)
        if ctrl is None:
            return
        # Must be cast by the controller
        caster = getattr(event, 'player', None) or getattr(event, 'controller', None)
        if caster is not ctrl:
            return
        # Must be an instant or sorcery
        spell = getattr(event, 'spell', None) or getattr(event, 'card', None)
        if spell is None:
            return
        card_types = getattr(spell, 'card_types', set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return
        # Check mana spent (use mana_cost.cmc as proxy for mana spent)
        mana_spent = getattr(event, 'mana_spent', None)
        if mana_spent is None:
            # Infer from the spell's mana cost
            mc = getattr(spell, 'mana_cost', None)
            if mc is not None:
                mana_spent = mc.cmc
            else:
                mana_spent = 0
        if mana_spent >= 5:
            # Create a token copy
            token = ColorstormStallion(owner=ctrl, controller=ctrl)
            token.is_token = True
            token._temp_power_bonus = 0
            token._temp_toughness_bonus = 0
            bf = game.get_battlefield(ctrl)
            bf.add(token)
            token.summoning_sick = False
            if hasattr(token, 'register_triggers'):
                token.register_triggers(game)
