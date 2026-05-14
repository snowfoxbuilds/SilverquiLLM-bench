"""Card implementation for High-Society Hunter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class HighSocietyHunter(Creature):
    """High-Society Hunter — {3}{B}{B} — 5/3 — Vampire Noble — Flying.

    Whenever this creature attacks, you may sacrifice another creature.
    If you do, put a +1/+1 counter on this creature.
    Whenever another nontoken creature dies, draw a card.

    FDN collector number 61.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "High-Society Hunter")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{B}"))
        kwargs.setdefault("subtypes", {"Vampire", "Noble"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhenever this creature attacks, you may sacrifice "
            "another creature. If you do, put a +1/+1 counter on this "
            "creature.\nWhenever another nontoken creature dies, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: "GameState") -> None:
        """Register attack trigger (sacrifice for +1/+1 counter) and death
        trigger (draw when another nontoken creature dies)."""
        from engine.game import add_counter, draw_card, sacrifice
        from engine.triggers import EventType, TriggerRegistration

        source = self

        # ------------------------------------------------------------------
        # Attack trigger: sacrifice another creature → +1/+1 counter
        # ------------------------------------------------------------------

        def _attack_condition(game: Any, data: dict) -> bool:
            """Fire when this creature attacks."""
            return data.get("creature") is source

        def _attack_effect(game: "GameState") -> None:
            """May sacrifice another creature; if so, add +1/+1 counter."""
            controller = getattr(source, "controller", None)
            if controller is None:
                return

            # Find other creatures on the battlefield we could sacrifice
            battlefield = game.get_battlefield(controller)
            candidates = [
                c for c in battlefield.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and c is not source
            ]
            if not candidates:
                return

            # Use controller.choose_card() for the optional sacrifice choice.
            # If controller declines (returns None), no sacrifice occurs.
            try:
                chosen = controller.choose_card(candidates, "sacrifice a creature for +1/+1 counter")
            except Exception:
                # DeterministicPlayer may raise if no queued choice — treat
                # as declining.
                chosen = None

            if chosen is None:
                return

            # Perform sacrifice
            sacrifice(game, controller, chosen)
            # Add +1/+1 counter
            add_counter(game, source, "+1/+1", 1)
            # Keep _original_plus_one_counters in sync so counters survive
            # the effect_manager reset cycle.
            if hasattr(source, "_original_plus_one_counters"):
                source._original_plus_one_counters = source.plus_one_counters

        # ------------------------------------------------------------------
        # Death trigger: another nontoken creature dies → draw a card
        # ------------------------------------------------------------------

        def _dies_condition(game: Any, data: dict) -> bool:
            """Fire when another nontoken creature dies."""
            creature = data.get("creature")
            if creature is source:
                return False  # "another" — not self
            if getattr(creature, "is_token", False):
                return False  # nontoken only
            return True

        def _dies_effect(game: "GameState") -> None:
            """Draw a card."""
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is not None:
                draw_card(game, controller)

        # Register both triggers
        controller = getattr(self, "controller", None) or game.active_player

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ATTACKS,
            condition=_attack_condition,
            effect=_attack_effect,
            source=self,
            controller=controller,
        ))

        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_dies_condition,
            effect=_dies_effect,
            source=self,
            controller=controller,
        ))
