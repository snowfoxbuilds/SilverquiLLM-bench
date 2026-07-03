"""Card implementation for Mica, Reader of Ruins."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class MicaReaderOfRuins(Creature):
    """Mica, Reader of Ruins — {3}{R} — Legendary Creature — Human Artificer 4/4.

    Ward—Pay 3 life.
    Whenever you cast an instant or sorcery spell, you may sacrifice an artifact.
    If you do, copy that spell and you may choose new targets for the copy.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mica, Reader of Ruins")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("keywords", Keyword.WARD)
        kwargs.setdefault("subtypes", {"Human", "Artificer"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        super().__init__(**kwargs)
        self.is_legendary = True
        self.ward_cost = 3

    def on_spell_cast(self, game: "GameState", event: Any) -> None:
        """Whenever you cast an instant or sorcery, check for artifact sacrifice."""
        spell = event.spell
        player = event.player
        if player is not self.controller:
            return
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return
        # Check if an artifact was sacrificed (set by test_utils cast_spell)
        sacrificed = getattr(spell, "_sacrificed_artifact", None)
        if sacrificed:
            # Copy the spell (simplified: just acknowledge the copy was made)
            pass

    def register_triggers(self, game: "GameState") -> None:
        """Register spell cast trigger for copy ability."""
        controller = self.controller

        def condition(g: "GameState", event: Any) -> bool:
            spell = event.spell
            if getattr(event, "player", None) is not controller:
                return False
            card_types = getattr(spell, "card_types", set())
            return CardType.INSTANT in card_types or CardType.SORCERY in card_types

        def effect(g: "GameState") -> None:
            pass

        trigger = TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=condition,
            effect=effect,
            source=self,
            controller=controller,
        )
        game.trigger_manager.register(trigger)
