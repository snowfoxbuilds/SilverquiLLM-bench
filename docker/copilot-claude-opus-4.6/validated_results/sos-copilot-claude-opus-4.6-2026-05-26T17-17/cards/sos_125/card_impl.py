"""Card implementation for Molten-Core Maestro."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class MoltenCoreMaestro(Creature):
    """Molten-Core Maestro — {1}{R} — Creature — Goblin Bard 2/2.

    Menace
    Opus — Whenever you cast an instant or sorcery spell, put a +1/+1 counter
    on this creature. If five or more mana was spent to cast that spell, add an
    amount of {R} equal to this creature's power.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Molten-Core Maestro")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("keywords", Keyword.MENACE)
        kwargs.setdefault("subtypes", {"Goblin", "Bard"})
        super().__init__(**kwargs)

    def on_spell_cast(self, game: "GameState", event: Any) -> None:
        """Opus trigger: +1/+1 counter, and if 5+ mana spent, add R equal to power."""
        spell = event.spell
        player = event.player
        if player is not self.controller:
            return
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return
        # Put a +1/+1 counter on this creature
        self.plus_one_counters += 1
        self._base_plus_one_counters = self.plus_one_counters
        # Check if 5 or more mana was spent
        mana_cost = getattr(spell, "mana_cost", None)
        if mana_cost is not None:
            total_spent = mana_cost.total()
            if total_spent >= 5:
                # Add R equal to this creature's power
                current_power = self.get_power()
                player.mana_pool.add(ManaType.RED, current_power)

    def register_triggers(self, game: "GameState") -> None:
        """Register spell cast trigger."""
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
