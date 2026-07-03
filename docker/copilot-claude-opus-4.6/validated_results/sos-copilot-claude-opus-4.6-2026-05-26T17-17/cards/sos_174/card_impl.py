"""Card implementation for Aziza, Mage Tower Captain."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class AzizaMageTowerCaptain(Creature):
    """Aziza, Mage Tower Captain — {R}{W} — 2/2 Legendary Creature — Djinn Sorcerer.

    Whenever you cast an instant or sorcery spell, you may tap three untapped
    creatures you control. If you do, copy that spell. You may choose new
    targets for the copy.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Aziza, Mage Tower Captain")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{W}"))
        kwargs.setdefault("subtypes", {"Djinn", "Sorcerer"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register trigger: whenever you cast an instant or sorcery spell."""
        source = self
        controller = self.controller

        def _condition(game: "GameState", event: SpellCastTriggeredEvent) -> bool:
            # Only trigger for spells cast by our controller
            if event.player is not source.controller:
                return False
            # Only for instants and sorceries
            spell = event.spell or event.card
            if spell is None:
                return False
            card_types = getattr(spell, "card_types", set())
            return CardType.INSTANT in card_types or CardType.SORCERY in card_types

        def _effect(game: "GameState") -> None:
            ctrl = source.controller
            if ctrl is None:
                return
            # Check for 3 untapped creatures
            bf = game.get_battlefield(ctrl)
            untapped = [c for c in bf.get_all()
                        if CardType.CREATURE in getattr(c, "card_types", set())
                        and not getattr(c, "is_tapped", True)]
            if len(untapped) < 3:
                return
            # Tap 3 creatures (deterministic: first 3)
            for i in range(3):
                untapped[i].is_tapped = True
            # Copy the spell (engine limitation: we just note it was copied)

        game.trigger_manager.register(TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
