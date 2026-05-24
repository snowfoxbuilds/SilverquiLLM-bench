"""Card implementation for Firespitter Whelp."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

class FirespitterWhelp(Creature):
    """Firespitter Whelp — {2}{R} — 2/2 — Dragon — Flying.

    Whenever you cast a noncreature or Dragon spell, this creature deals
    1 damage to each opponent.

    FDN collector number 197.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Firespitter Whelp')
        kwargs.setdefault('mana_cost', ManaCost.parse('{2}{R}'))
        kwargs.setdefault('subtypes', {'Dragon'})
        kwargs.setdefault('keywords', Keyword.FLYING)
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 2)
        kwargs.setdefault('rules_text', 'Flying\nWhenever you cast a noncreature or Dragon spell, this creature deals 1 damage to each opponent.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register noncreature-or-Dragon spell cast trigger."""
        from benchmarks.sos.workspace.engine.game import deal_damage
        from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
        source = self
        controller = getattr(self, 'controller', None) or game.active_player

        def _condition(game: Any, event: dict) -> bool:
            ctrl = getattr(source, 'controller', None)
            caster = event.player
            if caster is not ctrl:
                return False
            spell = event.spell
            if spell is None:
                return False
            card_types = getattr(spell, 'card_types', set())
            subtypes = getattr(spell, 'subtypes', set())
            is_noncreature = CardType.CREATURE not in card_types
            is_dragon = 'Dragon' in subtypes
            return is_noncreature or is_dragon

        def _effect(game: 'GameState') -> None:
            ctrl = getattr(source, 'controller', None)
            if ctrl is None:
                return
            for player in game.players:
                if player is not ctrl:
                    deal_damage(game, source, player, 1)
        game.trigger_manager.register(TriggerRegistration(event_type=SpellCastTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller))
