"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells from
    among them without paying their mana costs.

    Paradigm — Then exile this spell. After you first resolve a spell with
    this name, you may cast a copy of it from exile without paying its mana
    cost at the beginning of each of your first main phases.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards "
            "with total mana value 4 or greater. You may cast any number of "
            "spells from among them without paying their mana costs.\n"
            "Paradigm (Then exile this spell. After you first resolve a spell "
            "with this name, you may cast a copy of it from exile without paying "
            "its mana cost at the beginning of each of your first main phases.)",
        )
        super().__init__(**kwargs)
        # Paradigm state: True after first resolution.
        self.paradigm_active: bool = False
        # Exiled cards available for free casting after resolution.
        self.cards_from_capstone: list[Any] = []

    def on_resolve(self, game: "GameState") -> None:
        """Exile from top until MV >= 4, allow free casting; Paradigm exile."""
        controller = self.controller
        if controller is None:
            return

        library = controller.zones[Zone.LIBRARY]
        exiled: list[Any] = []
        total_mv = 0

        # Exile cards from top until total MV >= 4.
        while total_mv < 4:
            top = library.top(1)
            if not top:
                break
            card = top[0]
            library.remove(card)
            card_mv = getattr(card, "mana_cost", None)
            mv = card_mv.cmc if card_mv is not None else 0
            exiled.append(card)
            total_mv += mv
            controller.zones[Zone.EXILE].add(card)

        # Store exiled cards for player reference.
        self.cards_from_capstone = exiled

        # Free casting of exiled cards (simplified: mark as free_cast=True).
        for card in exiled:
            card.free_cast_available = True

        # Paradigm: exile this spell.
        if self in controller.zones.get(Zone.GRAVEYARD, type('Empty', (), {'get_all': list})()).get_all() if hasattr(controller.zones, 'get') else []:
            controller.zones[Zone.GRAVEYARD].remove(self)
            controller.zones[Zone.EXILE].add(self)

        # Also remove from graveyard if present (simpler check).
        gy = controller.zones[Zone.GRAVEYARD]
        if gy.contains(self):
            gy.remove(self)
            controller.zones[Zone.EXILE].add(self)

        # Activate Paradigm on first resolution.
        if not self.paradigm_active:
            self.paradigm_active = True
            self._register_paradigm_trigger(game, controller)

    def _register_paradigm_trigger(self, game: "GameState", controller: Any) -> None:
        """Register a recurring trigger for beginning of each first main phase."""
        source = self

        def _condition(game: "GameState", event: BeginningOfMainPhaseTriggeredEvent) -> bool:
            return (
                getattr(event, "player", None) is controller
                and getattr(event, "is_first_main", False)
                and source.paradigm_active
            )

        def _effect(game: "GameState") -> None:
            # Mark that a free copy can be cast this main phase.
            controller.paradigm_copy_available = getattr(
                controller, "paradigm_copy_available", 0
            ) + 1

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
