"""Card implementation for Rehearsed Debater."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class RehearsedDebater(Creature):
    """Rehearsed Debater — {2}{W} — Creature — Djinn Bard — 3/3.

    Vigilance
    Repartee — Whenever you cast an instant or sorcery spell that targets
    a creature, this creature gets +1/+1 until end of turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rehearsed Debater")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}"))
        kwargs.setdefault("subtypes", {"Djinn", "Bard"})
        kwargs.setdefault("keywords", Keyword.VIGILANCE)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Vigilance\n"
            "Repartee — Whenever you cast an instant or sorcery spell that "
            "targets a creature, this creature gets +1/+1 until end of turn.",
        )
        super().__init__(**kwargs)

    def on_spell_cast(self, game: "GameState", event: Any) -> None:
        """Repartee: when controller casts instant/sorcery targeting a creature, get +1/+1."""
        controller = self.controller
        if event.player is not controller:
            return
        spell = event.spell
        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return
        targets = getattr(event, "targets", None) or []
        for t in targets:
            t_types = getattr(t, "card_types", set())
            if CardType.CREATURE in t_types:
                if not hasattr(self, "_temp_power_bonus"):
                    self._temp_power_bonus = 0
                if not hasattr(self, "_temp_toughness_bonus"):
                    self._temp_toughness_bonus = 0
                self._temp_power_bonus += 1
                self._temp_toughness_bonus += 1
                return

    def register_triggers(self, game: "GameState") -> None:
        """Register the Repartee trigger."""
        controller = self.controller
        source = self

        def _condition(g: Any, event: Any) -> bool:
            # Must be our controller casting
            if event.player is not controller:
                return False
            # Must be instant or sorcery
            spell = event.spell
            card_types = getattr(spell, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            # Must target a creature
            targets = getattr(event, "targets", None) or []
            for t in targets:
                t_types = getattr(t, "card_types", set())
                if CardType.CREATURE in t_types:
                    return True
            return False

        def _effect(g: Any) -> None:
            # Give +1/+1 until end of turn
            if not hasattr(source, "_temp_power_bonus"):
                source._temp_power_bonus = 0
            if not hasattr(source, "_temp_toughness_bonus"):
                source._temp_toughness_bonus = 0
            source._temp_power_bonus += 1
            source._temp_toughness_bonus += 1

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
