"""Card implementation for Firebrand Archer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class FirebrandArcher(Creature):
    """Firebrand Archer — {1}{R} — 2/1 — Human Archer.

    Whenever you cast a noncreature spell, this creature deals 1 damage
    to each opponent.

    FDN collector number 196.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Firebrand Archer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("subtypes", {"Human", "Archer"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Whenever you cast a noncreature spell, this creature deals 1 "
            "damage to each opponent.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register noncreature spell cast trigger."""
        from engine.game import deal_damage
        from engine.triggers import EventType, TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        def _condition(game: Any, data: dict) -> bool:
            ctrl = getattr(source, "controller", None)
            caster = data.get("player")
            if caster is not ctrl:
                return False
            spell = data.get("spell")
            if spell is None:
                return False
            card_types = getattr(spell, "card_types", set())
            return CardType.CREATURE not in card_types

        def _effect(game: "GameState") -> None:
            ctrl = getattr(source, "controller", None)
            if ctrl is None:
                return
            for player in game.players:
                if player is not ctrl:
                    deal_damage(game, source, player, 1)

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.SPELL_CAST,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
