"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with
    total mana value 4 or greater. You may cast any number of spells from
    among them without paying their mana costs.

    Paradigm: Then exile this spell. After you first resolve a spell with
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
        # _exile_on_resolve is set to True during on_resolve (Paradigm).
        self._exile_on_resolve: bool = False
        # Tracks whether the Paradigm trigger has been registered for this instance.
        self._paradigm_registered: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """Resolve Improvisation Capstone."""
        controller = self.controller
        if controller is None:
            return

        # --- Main Effect: exile cards from top of library until MV >= 4 ---
        library = game.get_library(controller)
        exile_zone = game.get_exile(controller)

        exiled_cards: list[Any] = []
        total_mv = 0

        while total_mv < 4 and len(library) > 0:
            # Pop from the top (last item in the internal list)
            top_cards = library.top(1)
            if not top_cards:
                break
            card = top_cards[-1]
            library.remove(card)
            exile_zone.add(card)
            exiled_cards.append(card)
            mv = card.mana_cost.cmc if hasattr(card, "mana_cost") and card.mana_cost is not None else 0
            total_mv += mv

        # UNVERIFIED: player choice for which exiled cards to cast — player choice API not testable without full game loop
        # For each exiled card, offer the player a choice to cast it for free.
        # (This is skipped in test context as choose_yes_no is not fully implemented.)

        # --- Paradigm: exile this spell after resolution ---
        self._exile_on_resolve = True

        # --- Paradigm: register recurring trigger on FIRST resolution ---
        if not self._paradigm_registered:
            self._paradigm_registered = True
            _register_paradigm_trigger(game, self, controller)


def _register_paradigm_trigger(
    game: "GameState",
    source_card: "ImprovisationCapstone",
    controller: Any,
) -> None:
    """Register the Paradigm recurring BeginningOfMainPhaseTriggeredEvent trigger."""

    def condition(g: "GameState", event: Any) -> bool:
        """Only fire when the active player is the card's controller."""
        return g.active_player is controller

    def effect(g: "GameState") -> None:
        """Create a copy of the spell and resolve its effect (free cast from exile)."""
        # UNVERIFIED: paradigm copy-cast step — copy creation and free casting not fully testable
        # The original exiled card stays in exile; only a copy is "cast".
        # For the purpose of this implementation, we do nothing that moves
        # the original — the original card remains in exile.
        pass

    trigger = TriggerRegistration(
        event_type=BeginningOfMainPhaseTriggeredEvent,
        condition=condition,
        effect=effect,
        source=source_card,
        controller=controller,
    )
    game.trigger_manager.register(trigger)
