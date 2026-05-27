"""Card implementation for Molten-Core Maestro."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class MoltenCoreMaestro(Creature):
    """Molten-Core Maestro — {1}{R} — 2/2 — Goblin Bard — Menace.

    Opus — Whenever you cast an instant or sorcery spell, put a +1/+1
    counter on this creature. If five or more mana was spent to cast
    that spell, add an amount of {R} equal to this creature's power.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Molten-Core Maestro")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault("subtypes", {"Goblin", "Bard"})
        kwargs.setdefault("keywords", Keyword.MENACE)
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Menace\nOpus — Whenever you cast an instant or sorcery spell, "
            "put a +1/+1 counter on this creature. If five or more mana was "
            "spent to cast that spell, add an amount of {R} equal to this "
            "creature's power.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register the Opus triggered ability."""
        from engine.game import add_counter
        from engine.triggers import TriggerRegistration

        source = self
        controller = getattr(self, "controller", None) or game.active_player

        _captured_mana_spent: list[int] = [0]

        def _condition(game: Any, event: SpellCastTriggeredEvent) -> bool:
            ctrl = getattr(source, "controller", None)
            if event.player is not ctrl:
                return False
            spell = event.spell
            card_types = getattr(spell, "card_types", set())
            if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
                return False
            _captured_mana_spent[0] = getattr(event, "mana_spent", 0)
            return True

        def _effect(game: "GameState") -> None:
            add_counter(game, source, "+1/+1", 1)
            if hasattr(source, "_base_plus_one_counters"):
                source._base_plus_one_counters = source.plus_one_counters

            if _captured_mana_spent[0] >= 5:
                ctrl = getattr(source, "controller", None)
                if ctrl is not None:
                    power = source.power
                    if power > 0:
                        ctrl.mana_pool.add(ManaType.RED, power)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=self,
                controller=controller,
            )
        )

