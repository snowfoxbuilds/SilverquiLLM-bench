"""Card implementation for Firebrand Archer."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.events import SpellCastTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class FirebrandArcherAbility1:
    text = 'Whenever you cast a noncreature spell, this creature deals 1 damage to each opponent.'


# endregion Printed abilities


class FirebrandArcher(Creature):
    """Firebrand Archer — {1}{R} — 2/1 — Human Archer.

    Whenever you cast a noncreature spell, this creature deals 1 damage
    to each opponent.

    FDN collector number 196.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Firebrand Archer')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{R}'))
        kwargs.setdefault('subtypes', {'Human', 'Archer'})
        kwargs.setdefault('base_power', 2)
        kwargs.setdefault('base_toughness', 1)
        kwargs.setdefault('rules_text', 'Whenever you cast a noncreature spell, this creature deals 1 damage to each opponent.')
        super().__init__(**kwargs)

    def register_triggers(self, game: 'GameState') -> None:
        """Register noncreature spell cast trigger."""
        from engine.game import deal_damage
        from engine.triggers import TriggerRegistration
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
            return CardType.CREATURE not in card_types

        def _effect(game: 'GameState', controller: Any) -> None:
            ctrl = controller
            if ctrl is None:
                return
            for player in game.players:
                if player is not ctrl:
                    deal_damage(game, source, player, 1)
        game.trigger_manager.register(TriggerRegistration(event_type=SpellCastTriggeredEvent, condition=_condition, effect=_effect, source=self, controller=controller, printed=FirebrandArcherAbility1))
