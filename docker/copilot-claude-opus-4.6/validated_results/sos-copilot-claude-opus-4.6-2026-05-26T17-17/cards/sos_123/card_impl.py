"""Card implementation for Magmablood Archaic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class MagmabloodArchaic(Creature):
    """Magmablood Archaic — {2/R}{2/R}{2/R} — Creature — Avatar 2/2.

    Trample, reach
    Converge — This creature enters with a +1/+1 counter on it for each
    color of mana spent to cast it.
    Whenever you cast an instant or sorcery spell, creatures you control get
    +1/+0 until end of turn for each color of mana spent to cast that spell.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Magmablood Archaic")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2/R}{2/R}{2/R}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("keywords", Keyword.TRAMPLE | Keyword.REACH)
        kwargs.setdefault("subtypes", {"Avatar"})
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """Converge — enter with +1/+1 counters equal to colors of mana spent."""
        colors_spent = getattr(self, "colors_spent", [])
        num_colors = len(set(colors_spent))
        if num_colors > 0:
            self.plus_one_counters += num_colors
            self._base_plus_one_counters = self.plus_one_counters

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
            # Find the most recently cast spell's colors_spent
            # We need to check all objects on battlefield for the boost
            # The colors_spent is stored on the spell card
            # We use on_spell_cast instead for immediate access
            pass

        trigger = TriggerRegistration(
            event_type=SpellCastTriggeredEvent,
            condition=condition,
            effect=effect,
            source=self,
            controller=controller,
        )
        game.trigger_manager.register(trigger)

    def on_spell_cast(self, game: "GameState", event: Any) -> None:
        """Whenever you cast an instant or sorcery, boost creatures."""
        spell = event.spell
        player = event.player
        if player is not self.controller:
            return
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return
        # Count colors of mana spent
        colors_spent = getattr(spell, "colors_spent", [])
        num_colors = len(set(colors_spent))
        if num_colors <= 0:
            return
        # Give all creatures we control +N/+0 until end of turn
        bf = game.get_battlefield(self.controller)
        for obj in bf.get_all():
            if CardType.CREATURE in getattr(obj, "card_types", set()):
                bonus = getattr(obj, "_temp_power_bonus", 0)
                obj._temp_power_bonus = bonus + num_colors
